import os
import subprocess
import logging
from pathlib import Path
from time import sleep
from typing import Optional, Tuple, Dict, Any
import re
import json
from dataclasses import dataclass
from functools import lru_cache
from backend.db_operations import fetch, execute_with_retry, DatabaseError
from collections import deque

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %I:%M:%S %p"
)
logger = logging.getLogger(__name__)

@dataclass
class Config:
    """Configuration for video processing."""
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", "/video-output"))
    process_retry_delay: int = int(os.getenv("PROCESS_RETRY_DELAY", "30"))
    max_consecutive_errors: int = int(os.getenv("MAX_CONSECUTIVE_ERRORS", "3"))
    min_reduction_ratio: float = float(os.getenv("MIN_REDUCTION_RATIO", "0.2"))
    sleep_interval: int = int(os.getenv("SLEEP_INTERVAL", "10"))
    max_retry_delay: int = int(os.getenv("MAX_RETRY_DELAY", "300"))

    def validate(self):
        """Validate configuration values."""
        if self.min_reduction_ratio <= 0 or self.min_reduction_ratio > 1:
            raise ValueError("MIN_REDUCTION_RATIO must be between 0 and 1.")
        if self.process_retry_delay <= 0:
            raise ValueError("PROCESS_RETRY_DELAY must be greater than 0.")
        if self.max_consecutive_errors <= 0:
            raise ValueError("MAX_CONSECUTIVE_ERRORS must be greater than 0.")
        if self.sleep_interval <= 0:
            raise ValueError("SLEEP_INTERVAL must be greater than 0.")
        if self.max_retry_delay <= 0:
            raise ValueError("MAX_RETRY_DELAY must be greater than 0.")

CONFIG = Config()
CONFIG.validate()

# SQL Queries
SQL_QUERIES = {
    "get_next_video": """
        SELECT * FROM videos WHERE status = 'ready' ORDER BY created_at ASC LIMIT 1
    """,
    "update_progress": """
        UPDATE videos SET progress = ? WHERE id = ?
    """,
    "update_status_failed": """
        UPDATE videos SET status = 'failed' WHERE id = ?
    """,
    "update_status_confirmed": """
        UPDATE videos SET status = 're-confirmed' WHERE id = ?
    """,
    "update_estimated_size": """
        UPDATE videos SET estimated_size = ?, WHERE id = ?
    """,
    "update_status_optimized": """
        UPDATE videos
        SET optimized_size = ?, status = 'optimized',
            optimized_path = ?, new_codec = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """
}

def get_next_ready_video() -> Optional[Dict[str, Any]]:
    """Fetch the next video ready for processing from the database."""
    try:
        return fetch(SQL_QUERIES["get_next_video"], None, None, True)
    except DatabaseError as e:
        logger.error(f"Failed to fetch next ready video: {e}")
        return None

@lru_cache(maxsize=128)
def parse_ffprobe_data(ffprobe_json: str) -> Dict[str, Any]:
    """Parse ffprobe JSON data with caching to avoid redundant parsing."""
    try:
        return json.loads(ffprobe_json)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse ffprobe data: {e}")
        return {}

def parse_ffmpeg_progress_line(line: str) -> Dict[str, float]:
    """Parse ffmpeg progress line to extract time and size."""
    time_match = re.search(r'time=(\d+):(\d+):(\d+)\.(\d+)', line)
    current_time = 0.0
    if time_match:
        h, m, s, ms = map(int, time_match.groups())
        current_time = h * 3600 + m * 60 + s + ms / 100.0
    else:
        current_time_match = re.search(r'time=(\d+\.\d+)', line)
        if current_time_match:
            current_time = float(current_time_match.group(1))

    size_match = re.search(r'size=\s*(\d+)\s*kB', line)
    current_size = float(size_match.group(1)) * 1024 if size_match else 0.0

    return {"time": current_time, "size": current_size}

def execute_ffmpeg_command(command_list: list, video_id: int, total_duration: float, original_size: int) -> Tuple[bool, str, str]:
    """Execute the ffmpeg command and track progress with smart size estimation."""
    try:
        bitrate_window = deque(maxlen=5) 
        with subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        ) as process:
            for line in process.stderr:
                if "frame=" in line:
                    try:
                        execute_with_retry(SQL_QUERIES["update_progress"], (line.strip(), video_id))
                    except DatabaseError as db_err:
                        logger.error(f"Failed to update progress for video {video_id}: {db_err}")

                    parsed = parse_ffmpeg_progress_line(line)
                    current_time = parsed["time"]
                    current_size = parsed["size"]

                    if current_time > 10 and total_duration > 0:
                        current_bitrate = current_size / current_time
                        bitrate_window.append(current_bitrate)
                        avg_bitrate = sum(bitrate_window) / len(bitrate_window)

                        estimated_final_size = avg_bitrate * total_duration
                        reduction_ratio = 1 - (estimated_final_size / original_size)

                        execute_with_retry(SQL_QUERIES["update_estimated_size"], (estimated_final_size, video_id))

                        logger.info(
                            f"Estimated final size: {estimated_final_size / 1024 / 1024:.2f} MB "
                            f"({reduction_ratio * 100:.2f}% reduction)"
                        )

                        if reduction_ratio < CONFIG.min_reduction_ratio:
                            logger.warning(f"Early exit: Reduction {reduction_ratio:.2%} is below threshold.")
                            execute_with_retry(SQL_QUERIES["update_status_confirmed"], (video_id,))
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                logger.warning("Forced termination due to timeout.")
                                process.kill()
                                process.wait()
                            return False, "", "ok"

            return_code = process.wait(timeout=10)
            if return_code != 0:
                logger.error(f"ffmpeg failed with return code {return_code}")
                return False, "", "not ok"

        return True, "", "ok"
    except subprocess.TimeoutExpired:
        logger.warning("Timeout while waiting for ffmpeg. Killing process.")
        process.kill()
        process.wait()
        return False, "", "timeout"
    except Exception as e:
        logger.exception(f"Unexpected error during ffmpeg execution: {e}")
        return False, "", "error"

def run_ffmpeg(input_path: str, output_path: str, video: Dict[str, Any]) -> Tuple[bool, str, str]:
    """Execute ffmpeg command to process the video."""
    try:
        video_id = video["id"]
        command_str = video["ai_command"]
        original_size = video["original_size"]
        ffprobe_data = parse_ffprobe_data(video["ffprobe_data"])
        total_duration = float(ffprobe_data.get("duration", 0))

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        command_list = command_str.split()
        command_list[command_list.index("input.mp4")] = input_path
        command_list[command_list.index("output.mp4")] = str(output_path)

        logger.info(f"Executing ffmpeg: {' '.join(command_list)}")
        return execute_ffmpeg_command(command_list, video_id, total_duration, original_size)
    except Exception as e:
        logger.exception(f"Error in run_ffmpeg: {e}")
        return False, "", "error"

def update_video_status(video_id: int, optimized_size: int, output_path: str, codec: str) -> bool:
    """Update video status in the database after processing."""
    try:
        execute_with_retry(
            SQL_QUERIES["update_status_optimized"],
            (optimized_size, output_path, codec, video_id)
        )
        return True
    except DatabaseError as e:
        logger.error(f"Failed to update video status for video {video_id}: {e}")
        return False

def process_video(video: Dict[str, Any]) -> bool:
    """Process a single video and handle its lifecycle."""
    input_path = Path(video["filepath"])
    output_path = CONFIG.output_dir / input_path.name

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        execute_with_retry(SQL_QUERIES["update_status_failed"], (video["id"],))
        return False

    try:
        success, codec, status = run_ffmpeg(str(input_path), str(output_path), video)
        if success:
            optimized_size = output_path.stat().st_size
            if update_video_status(video["id"], optimized_size, str(output_path), codec):
                logger.info(f"Successfully optimized video: {input_path.name}")
                return True
        elif status == "ok" and not success:
            logger.error(f"Processing failed due to threshold not reached: {input_path.name}")
            execute_with_retry(SQL_QUERIES["update_status_confirmed"], (video["id"],))
        else:
            logger.warning(f"Processing failed for video: {input_path.name}")
            execute_with_retry(SQL_QUERIES["update_status_failed"], (video["id"],))
    except Exception as e:
        logger.exception(f"Error processing video {input_path.name}: {e}")
        execute_with_retry(SQL_QUERIES["update_status_failed"], (video["id"],))

    return False

def main():
    """Main loop for continuous video processing."""
    logger.info("Starting video processor...")
    consecutive_errors = 0

    while True:
        try:
            video = get_next_ready_video()
            if video:
                if process_video(video):
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
            else:
                logger.debug("No videos to process. Sleeping...")
                sleep(CONFIG.sleep_interval)
                continue

            if consecutive_errors >= CONFIG.max_consecutive_errors:
                logger.warning(f"Reached {consecutive_errors} consecutive errors. Taking a longer break...")
                sleep(CONFIG.process_retry_delay * 2)
                consecutive_errors = 0
            elif consecutive_errors > 0:
                sleep(CONFIG.process_retry_delay)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal. Exiting gracefully...")
            break
        except Exception as e:
            consecutive_errors += 1
            logger.exception(f"Main loop error: {e}")
            delay = min(CONFIG.process_retry_delay * (2 ** consecutive_errors), CONFIG.max_retry_delay)
            logger.info(f"Waiting {delay} seconds before retry...")
            sleep(delay)

            if consecutive_errors >= CONFIG.max_consecutive_errors:
                logger.critical(f"Too many consecutive errors ({consecutive_errors}). Exiting...")
                raise SystemExit(1)

if __name__ == "__main__":
    main()