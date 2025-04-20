import os
import time
from backend.utils import logger
from pathlib import Path
from typing import Iterator, Optional, List
import json
import subprocess
from backend.db_operations import (
    get_video_by_path,
    insert_video as db_insert_video,
    DatabaseError
)

# === Configuration ===
VIDEO_DIR = os.getenv("VIDEO_DIR", "/video-input")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 30))
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov'}


# === Utilities ===
def get_video_files(directory: str) -> Iterator[Path]:
    """Yield video file paths under given directory recursively."""
    for path in Path(directory).rglob("*"):
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            yield path.resolve()


def get_video_metadata_and_codec(filepath: Path) -> Optional[dict]:
    """Return both metadata and codec name for a video file."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name", str(filepath)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Parse the result to get both metadata and codec
        data = result.stdout
        return json.loads(data)
    except FileNotFoundError:
        logger.error("ffprobe not found in PATH.")
    except subprocess.CalledProcessError as e:
        logger.warning(f"ffprobe failed for {filepath.name}: {e.stderr}")
    return None


# === Main Scanner ===
def scan_and_insert() -> None:
    """
    Scan for new video files and insert them into the database.
    Uses the new database operations module with proper concurrency handling.
    """
    logger.info("Scanning for new video files...")
    new_files: List[Path] = []

    for filepath in get_video_files(VIDEO_DIR):
        try:
            # Check if file exists using the new db_operations module
            if get_video_by_path(str(filepath)):
                continue

            data = get_video_metadata_and_codec(filepath)
            if not data:
                continue

            # Extract metadata and codec
            metadata = json.dumps(data['format'], indent=2)
            codec = data['streams'][0]['codec_name'] if 'streams' in data and data['streams'] else 'Unknown'
            size = filepath.stat().st_size

            # Insert video using the new db_operations module
            try:
                db_insert_video(
                    filepath=str(filepath),
                    filename=filepath.name,
                    metadata=metadata,
                    codec=codec,
                    size=size
                )
                new_files.append(filepath)
                logger.debug(f"Successfully inserted video: {filepath.name}")
            except DatabaseError as e:
                logger.error(f"Failed to insert video {filepath.name}: {e}")

        except Exception as e:
            logger.error(f"Error processing file {filepath}: {e}")
            continue

    if new_files:
        logger.info(f"Inserted {len(new_files)} new videos into the database.")
    else:
        logger.info("No new videos found.")


def main() -> None:
    """
    Main function that runs the scanner in a continuous loop.
    Includes improved error handling and logging.
    """
    logger.info("Starting video directory scanner...")
    consecutive_errors = 0
    max_consecutive_errors = 3
    base_delay = SCAN_INTERVAL
    
    while True:
        try:
            scan_and_insert()
            consecutive_errors = 0  # Reset error counter on success
            time.sleep(base_delay)
            
        except Exception as e:
            consecutive_errors += 1
            logger.exception(f"Error during scan (attempt {consecutive_errors}): {e}")
            
            # Implement exponential backoff
            delay = min(base_delay * (2 ** consecutive_errors), 300)  # Max 5 minutes
            logger.info(f"Waiting {delay} seconds before next attempt...")
            
            # If too many consecutive errors, exit
            if consecutive_errors >= max_consecutive_errors:
                logger.critical(f"Too many consecutive errors ({consecutive_errors}). Exiting...")
                raise SystemExit(1)
                
            time.sleep(delay)


if __name__ == "__main__":
    main()

