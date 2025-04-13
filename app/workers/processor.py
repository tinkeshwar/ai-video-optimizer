import os
from sqlite3 import connect, Row
from time import sleep
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "/data/video_db.sqlite")
OUTPUT_DIR = Path("/video-output")

def get_db():
    try:
        conn = connect(DB_PATH)
        conn.row_factory = Row
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

def get_ready_videos():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos WHERE status = 'ready' LIMIT 100")  # Add limit for batch processing
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error fetching ready videos: {e}")
        return []

def run_ffmpeg(input_path: str, command_str: str, output_path: str) -> bool:
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        command_list = command_str.split()
        input_idx = command_list.index("input.mp4")
        output_idx = command_list.index("output.mp4")
        command_list[input_idx] = input_path
        command_list[output_idx] = output_path
        
        logger.info(f"Running ffmpeg command: {' '.join(command_list)}")
        subprocess.run(command_list, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg failed: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error in run_ffmpeg: {e}")
        return False

def update_video(video_id: int, optimized_size: int, output_path: str) -> None:
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE videos SET optimized_size = ?, status = 'optimized', optimized_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (optimized_size, output_path, video_id)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error updating video {video_id}: {e}")
        raise

def process_video(video: Row) -> None:
    input_path = video["filepath"]
    filename = os.path.basename(input_path)
    output_path = str(OUTPUT_DIR / filename)

    if not os.path.exists(input_path):
        logger.error(f"Input file not found: {input_path}")
        return

    if run_ffmpeg(input_path, video["ai_command"], output_path):
        try:
            optimized_size = os.path.getsize(output_path)
            update_video(video["id"], optimized_size, output_path)
            logger.info(f"Successfully optimized: {filename}")
        except OSError as e:
            logger.error(f"Error processing {filename}: {e}")

def main():
    logger.info("Starting video processor...")
    while True:
        try:
            videos = get_ready_videos()
            for video in videos:
                process_video(video)
            sleep(10)
        except KeyboardInterrupt:
            logger.info("Shutting down video processor...")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            sleep(30)  # Longer sleep on error

if __name__ == "__main__":
    main()
