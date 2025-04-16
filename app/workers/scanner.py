import os
import time
import sqlite3
import subprocess
import logging
from pathlib import Path
from typing import Iterator, Optional, List
import json

# === Configuration ===
VIDEO_DIR = os.getenv("VIDEO_DIR", "/video-input")
DB_PATH = os.getenv("DB_PATH", "/data/video_db.sqlite")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 30))
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov'}

# === Logger Setup ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


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


def file_already_exists(cursor: sqlite3.Cursor, path: Path) -> bool:
    cursor.execute("SELECT 1 FROM videos WHERE filepath = ? LIMIT 1", (str(path),))
    return cursor.fetchone() is not None


def insert_video(cursor: sqlite3.Cursor, filepath: Path, metadata: str, codec: str, size: int) -> None:
    cursor.execute("""
        INSERT INTO videos (filename, filepath, ffprobe_data, status, original_size, original_codec)
        VALUES (?, ?, ?, 'pending', ?, ?)
    """, (filepath.name, str(filepath), metadata, size, codec))


# === Main Scanner ===
def scan_and_insert() -> None:
    logger.info("Scanning for new video files...")
    new_files: List[Path] = []

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        for filepath in get_video_files(VIDEO_DIR):
            if file_already_exists(cursor, filepath):
                continue

            data = get_video_metadata_and_codec(filepath)

            if data:
                # Extract metadata and codec
                metadata = json.dumps(data['format'], indent=2)
                codec = data['streams'][0]['codec_name'] if 'streams' in data and data['streams'] else 'Unknown'
                size = filepath.stat().st_size
                insert_video(cursor, filepath, metadata, codec, size)
                new_files.append(filepath)

        if new_files:
            conn.commit()
            logger.info(f"Inserted {len(new_files)} new videos into the database.")
        else:
            logger.info("No new videos found.")



def main() -> None:
    logger.info("Starting video directory scanner...")
    while True:
        try:
            scan_and_insert()
        except Exception as e:
            logger.exception(f"Error during scan: {e}")
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
