import os
import subprocess
import logging
from pathlib import Path
from sqlite3 import connect, Row
from time import sleep
from typing import Optional, Tuple
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %I:%M:%S %p")
logger = logging.getLogger(__name__)

# Constants
DB_PATH = os.getenv("DB_PATH", "/data/video_db.sqlite")
OUTPUT_DIR = Path("/video-output")

if not DB_PATH:
    raise ValueError("DB_PATH environment variable is required")

@contextmanager
def get_db():
    conn = connect(DB_PATH)
    conn.row_factory = Row
    try:
        yield conn
    finally:
        conn.close()

def get_next_ready_video() -> Optional[Row]:
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos WHERE status = 'ready' LIMIT 1")
            row = cursor.fetchone()
            return row
    except Exception as e:
        logger.error(f"Error fetching next ready video: {e}")
        return None

def run_ffmpeg(input_path: str, command_str: str, output_path: str) -> Tuple[bool, str]:
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

def update_video(video_id: int, optimized_size: int, output_path: str, codec: str) -> None:
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE videos
                SET optimized_size = ?, status = 'optimized',
                    optimized_path = ?, new_codec = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (optimized_size, str(output_path), codec, video_id)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update video {video_id}: {e}")

def process_video(video: Row) -> None:
    input_path = Path(video["filepath"])
    output_path = OUTPUT_DIR / input_path.name

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return

    success, codec = run_ffmpeg(str(input_path), video["ai_command"], str(output_path))
    if success:
        try:
            optimized_size = output_path.stat().st_size
            update_video(video["id"], optimized_size, str(output_path), codec)
            logger.info(f"Video optimized: {input_path.name}")
        except OSError as e:
            logger.error(f"Error saving optimized data for {input_path.name}: {e}")

def main():
    logger.info("Video processor started (one-at-a-time mode)...")
    while True:
        try:
            video = get_next_ready_video()
            if video:
                process_video(video)
            else:
                logger.info("No videos to process. Sleeping...")
                sleep(10)
        except Exception as e:
            logger.error(f"Unhandled error in main loop: {e}")
            sleep(30)

if __name__ == "__main__":
    main()
