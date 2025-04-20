import os
import subprocess
import logging
from pathlib import Path
from time import sleep
from typing import Tuple, Dict, Any
import re
import json
from dataclasses import dataclass
from functools import lru_cache
from backend.db_operations import (
    get_next_ready_video,
    execute_with_retry,
    update_video_progress,
    update_video_status,
    update_video_estimated_size,
    update_final_output,
    DatabaseError
    )

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

CONFIG = Config()

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
    if time_match:
        h, m, s, ms = map(int, time_match.groups())
        current_time = h * 3600 + m * 60 + s + ms / 100.0
    else:
        current_time_match = re.search(r'time=(\d+\.\d+)', line)
        current_time = float(current_time_match.group(1)) if current_time_match else 0.0

    size_match = re.search(r'size=\s*(\d+)\s*kB', line)
    current_size = float(size_match.group(1)) * 1024 if size_match else 0.0

    return {"time": current_time, "size": current_size}

def run_ffmpeg(input_path: str, output_path: str, video: Dict[str, Any]) -> Tuple[bool, str]:
    """Execute ffmpeg command to process the video with progress tracking."""
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

        with subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        ) as process:
            try:
                for line in process.stderr:
                    if "frame=" in line:
                        try:
                            update_video_progress(video_id, line.strip())
                        except DatabaseError as db_err:
                            logger.error(f"Failed to update progress for video {video_id}: {db_err}")

                        parsed = parse_ffmpeg_progress_line(line)
                        current_time = parsed["time"]
                        current_size = parsed["size"]

                        if current_time > 10 and total_duration > 0:
                            estimated_final_size = (current_size / current_time) * total_duration
                            reduction_ratio = 1 - (estimated_final_size / original_size)
                            update_video_estimated_size(video_id, int(estimated_final_size))
                            if reduction_ratio < CONFIG.min_reduction_ratio:
                                logger.info(f"Early abort: Reduction ratio {reduction_ratio*100:.2f}% below threshold.")
                                process.terminate()
                                process.wait(timeout=5)
                                update_video_status(video_id, "re-confirmed")
                                return False, ""
            except subprocess.TimeoutExpired:
                logger.warning("Process termination timeout. Forcing kill.")
                process.kill()
                process.wait()

            return_code = process.wait(timeout=10)
            if return_code != 0:
                logger.error(f"ffmpeg failed with return code {return_code}")
                return False, ""

        codec = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1", str(output_path)
            ],
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()

        return True, codec

    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg subprocess error: {e.stderr}")
        return False, ""
    except Exception as e:
        logger.exception(f"Unexpected error in run_ffmpeg: {e}")
        return False, ""


def process_video(video: Dict[str, Any]) -> bool:
    """Process a single video and handle its lifecycle."""
    input_path = Path(video["filepath"])
    output_path = CONFIG.output_dir / input_path.name

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        update_video_status(video["id"], "failed")
        return False

    try:
        success, codec = run_ffmpeg(str(input_path), str(output_path), video)
        if success:
            optimized_size = output_path.stat().st_size
            if update_final_output(video["id"], str(output_path), codec, optimized_size):
                logger.info(f"Successfully optimized video: {input_path.name}")
                return True
        else:
            logger.warning(f"Processing failed for video: {input_path.name}")
            update_video_status(video["id"], "failed")
    except Exception as e:
        logger.exception(f"Error processing video {input_path.name}: {e}")
        update_video_status(video["id"], "failed")

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