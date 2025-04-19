import os
import subprocess
import logging
from pathlib import Path
from time import sleep
from typing import Optional, Tuple, Dict, Any
import re
import json
from backend.db_operations import fetch, execute_with_retry, DatabaseError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %I:%M:%S %p"
)
logger = logging.getLogger(__name__)

# Constants
OUTPUT_DIR = Path("/video-output")
PROCESS_RETRY_DELAY = int(os.getenv("PROCESS_RETRY_DELAY", "30"))
MAX_CONSECUTIVE_ERRORS = int(os.getenv("MAX_CONSECUTIVE_ERRORS", "3"))

SQL_GET_NEXT_VIDEO = """
    SELECT * FROM videos WHERE status = 'ready' ORDER BY created_at ASC LIMIT 1
"""
SQL_UPDATE_PROGRESS = """
    UPDATE videos SET progress = ? WHERE id = ?
"""
SQL_UPDATE_STATUS_FAILED = """
    UPDATE videos SET status = 'failed' WHERE id = ?
"""
SQL_UPDATE_STATUS_CONFIRMED = """
    UPDATE videos SET estimated_size = ?, status = 're-confirmed' WHERE id = ?
"""
SQL_UPDATE_STATUS_OPTIMIZED = """
    UPDATE videos
    SET optimized_size = ?, status = 'optimized',
        optimized_path = ?, new_codec = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
"""


def get_next_ready_video() -> Optional[Dict[str, Any]]:
    """Fetch the next video ready for processing."""
    try:
        return fetch(SQL_GET_NEXT_VIDEO, None, None, True)
    except DatabaseError as e:
        logger.error(f"Error fetching next ready video: {e}")
        return None


def parse_ffmpeg_progress_line(line: str) -> Dict[str, float]:
    """Parse ffmpeg progress line for time and size."""
    time_match = re.search(r'time=(\d+):(\d+):(\d+).(\d+)', line)
    if time_match:
        h, m, s, ms = map(int, time_match.groups())
        current_time = h * 3600 + m * 60 + s + ms / 100.0
    else:
        current_time_match = re.search(r'time=(\d+(\.\d+)?)', line)
        current_time = float(current_time_match.group(1)) if current_time_match else 0

    size_match = re.search(r'size=\s*(\d+)\s*kB', line)
    current_size = float(size_match.group(1)) * 1024 if size_match else 0

    return {"time": current_time, "size": current_size}


def run_ffmpeg(input_path: str, output_path: str, video: Dict[str, Any]) -> Tuple[bool, str]:
    """Run ffmpeg command to process the video."""
    try:
        video_id = video["id"]
        command_str = video["ai_command"]
        original_size = video["original_size"]
        ffprobe_data = json.loads(video["ffprobe_data"])
        total_duration = float(ffprobe_data.get("duration", 0))

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        command_list = command_str.split()
        command_list[command_list.index("input.mp4")] = str(input_path)
        command_list[command_list.index("output.mp4")] = str(output_path)

        logger.info(f"Running ffmpeg: {' '.join(command_list)}")

        with subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        ) as process:
            for line in process.stderr:
                if "frame=" in line:
                    try:
                        execute_with_retry(SQL_UPDATE_PROGRESS, (line.strip(), video_id))
                    except Exception as db_err:
                        logger.error(f"Failed to update progress for video {video_id}: {db_err}")

                    parsed = parse_ffmpeg_progress_line(line)
                    current_time = parsed["time"]
                    current_size = parsed["size"]

                    if current_time > 10 and total_duration > 0:
                        estimated_final_size = (current_size / current_time) * total_duration
                        reduction_ratio = 1 - (estimated_final_size / original_size)

                        if reduction_ratio < 0.2:
                            logger.info(f"Early abort: Estimated reduction {reduction_ratio*100:.2f}% is below threshold.")
                            process.terminate()
                            process.wait()

                            execute_with_retry(SQL_UPDATE_STATUS_CONFIRMED, (int(estimated_final_size), video_id))
                            return False, ""

            process.wait()

            if process.returncode != 0:
                logger.error(f"ffmpeg failed with return code {process.returncode}")
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
        logger.error(f"ffmpeg failed: {e.stderr}")
        return False, ""
    except Exception as e:
        logger.exception(f"Error in run_ffmpeg: {e}")
        return False, ""


def update_video_status(video_id: int, optimized_size: int, output_path: str, codec: str) -> bool:
    """Update video status after processing."""
    try:
        execute_with_retry(
            SQL_UPDATE_STATUS_OPTIMIZED,
            (optimized_size, str(output_path), codec, video_id)
        )
        return True
    except DatabaseError as e:
        logger.error(f"Failed to update video {video_id}: {e}")
        return False


def process_video(video: Dict[str, Any]) -> bool:
    """Process a single video."""
    input_path = Path(video["filepath"])
    output_path = OUTPUT_DIR / input_path.name

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return False

    try:
        success, codec = run_ffmpeg(str(input_path), str(output_path), video)
        if success:
            optimized_size = output_path.stat().st_size
            if update_video_status(video["id"], optimized_size, str(output_path), codec):
                logger.info(f"Video optimized: {input_path.name}")
                return True
        else:
            execute_with_retry(SQL_UPDATE_STATUS_FAILED, (video["id"],))
    except Exception as e:
        logger.exception(f"Error processing video {input_path.name}: {e}")
        execute_with_retry(SQL_UPDATE_STATUS_FAILED, (video["id"],))

    return False


def main():
    """Main function to process videos."""
    logger.info("Video processor started...")
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
                logger.info("No videos to process. Sleeping...")
                sleep(10)
                continue

            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                logger.warning(f"Hit {consecutive_errors} consecutive errors. Taking a longer break...")
                sleep(PROCESS_RETRY_DELAY * 2)
                consecutive_errors = 0
            elif consecutive_errors > 0:
                sleep(PROCESS_RETRY_DELAY)

        except Exception as e:
            consecutive_errors += 1
            logger.exception(f"Unhandled error in main loop: {e}")
            delay = min(PROCESS_RETRY_DELAY * (2 ** consecutive_errors), 300)
            logger.info(f"Waiting {delay} seconds before next attempt...")
            sleep(delay)

            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                logger.critical(f"Too many consecutive errors ({consecutive_errors}). Exiting...")
                raise SystemExit(1)


if __name__ == "__main__":
    main()
