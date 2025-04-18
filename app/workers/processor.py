import os
import subprocess
import logging
from pathlib import Path
from time import sleep
from typing import Optional, Tuple, Dict, Any
from backend.db_operations import (
    fetch_one,
    execute_with_retry,
    DatabaseError
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %I:%M:%S %p")
logger = logging.getLogger(__name__)

# Constants
OUTPUT_DIR = Path("/video-output")
PROCESS_RETRY_DELAY = int(os.getenv("PROCESS_RETRY_DELAY", "30"))
MAX_CONSECUTIVE_ERRORS = int(os.getenv("MAX_CONSECUTIVE_ERRORS", "3"))

def get_next_ready_video() -> Optional[Dict[str, Any]]:
    """
    Get the next video that's ready for processing.
    Uses the new database operations module with proper concurrency handling.
    """
    try:
        return fetch_one(
            "SELECT * FROM videos WHERE status = 'ready' ORDER BY created_at ASC LIMIT 1"
        )
    except DatabaseError as e:
        logger.error(f"Error fetching next ready video: {e}")
        return None

def run_ffmpeg(input_path: str, command_str: str, output_path: str) -> Tuple[bool, str]:
    """
    Run ffmpeg command to process the video.
    Returns success status and output codec.
    """
    try:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        command_list = command_str.split()
        command_list[command_list.index("input.mp4")] = str(input_path)
        command_list[command_list.index("output.mp4")] = str(output_path)

        logger.info(f"Running ffmpeg: {' '.join(command_list)}")
        subprocess.run(command_list, check=True, capture_output=True, text=True)

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
        logger.error(f"Error in run_ffmpeg: {e}")
        return False, ""

def update_video_status(video_id: int, optimized_size: int, output_path: str, codec: str) -> bool:
    """
    Update video status after processing.
    Uses the new database operations module with proper concurrency handling.
    """
    try:
        execute_with_retry(
            """
            UPDATE videos
            SET optimized_size = ?, status = 'optimized',
                optimized_path = ?, new_codec = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (optimized_size, str(output_path), codec, video_id)
        )
        return True
    except DatabaseError as e:
        logger.error(f"Failed to update video {video_id}: {e}")
        return False

def process_video(video: Dict[str, Any]) -> bool:
    """
    Process a single video.
    Returns True if processing was successful, False otherwise.
    """
    input_path = Path(video["filepath"])
    output_path = OUTPUT_DIR / input_path.name

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return False

    try:
        # Mark video as processing
        execute_with_retry(
            "UPDATE videos SET status = 'processing' WHERE id = ?",
            (video["id"],)
        )

        success, codec = run_ffmpeg(str(input_path), video["ai_command"], str(output_path))
        if success:
            try:
                optimized_size = output_path.stat().st_size
                if update_video_status(video["id"], optimized_size, str(output_path), codec):
                    logger.info(f"Video optimized: {input_path.name}")
                    return True
            except OSError as e:
                logger.error(f"Error saving optimized data for {input_path.name}: {e}")
                # Mark video as failed
                execute_with_retry(
                    "UPDATE videos SET status = 'failed' WHERE id = ?",
                    (video["id"],)
                )
        else:
            # Mark video as failed
            execute_with_retry(
                "UPDATE videos SET status = 'failed' WHERE id = ?",
                (video["id"],)
            )
    except DatabaseError as e:
        logger.error(f"Database error while processing video {input_path.name}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error while processing video {input_path.name}: {e}")
        try:
            execute_with_retry(
                "UPDATE videos SET status = 'failed' WHERE id = ?",
                (video["id"],)
            )
        except DatabaseError as db_err:
            logger.error(f"Failed to update video status to failed: {db_err}")

    return False

def main():
    """
    Main function that runs the video processor.
    Includes improved error handling, retries, and logging.
    """
    logger.info("Video processor started (one-at-a-time mode)...")
    consecutive_errors = 0
    
    while True:
        try:
            video = get_next_ready_video()
            if video:
                if process_video(video):
                    consecutive_errors = 0  # Reset error counter on success
                else:
                    consecutive_errors += 1
            else:
                consecutive_errors = 0  # Reset error counter when no work to do
                logger.info("No videos to process. Sleeping...")
                sleep(10)
                continue

            # If too many consecutive errors, take a longer break
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                logger.warning(f"Hit {consecutive_errors} consecutive errors. Taking a longer break...")
                sleep(PROCESS_RETRY_DELAY * 2)
                consecutive_errors = 0  # Reset after break
            elif consecutive_errors > 0:
                sleep(PROCESS_RETRY_DELAY)

        except Exception as e:
            consecutive_errors += 1
            logger.exception(f"Unhandled error in main loop (attempt {consecutive_errors}): {e}")
            
            # Implement exponential backoff
            delay = min(PROCESS_RETRY_DELAY * (2 ** consecutive_errors), 300)  # Max 5 minutes
            logger.info(f"Waiting {delay} seconds before next attempt...")
            sleep(delay)

            # If too many consecutive errors, exit
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                logger.critical(f"Too many consecutive errors ({consecutive_errors}). Exiting...")
                raise SystemExit(1)

if __name__ == "__main__":
    main()

