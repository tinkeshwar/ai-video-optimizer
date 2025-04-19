#!/usr/bin/env python3

import os
import shutil
import time
import logging
from backend.db_operations import (
    get_videos_by_status,
    update_video_status
)

REPLACE_BATCH_SIZE = int(os.getenv("REPLACE_BATCH_SIZE", 5))  # Default batch size
REPLACE_INTERVAL = int(os.getenv("REPLACE_INTERVAL", 10))     # Sleep between batches

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %I:%M:%S %p")
logger = logging.getLogger(__name__)

def replace_files(original_path: str, optimized_path: str, video_id: int) -> bool:
    try:
        if not os.path.exists(original_path):
            logger.error(f"[Missing] Original file does not exist: {original_path}")
            update_video_status(video_id, 'failed')
            return False

        if not os.path.exists(optimized_path):
            logger.error(f"[Missing] Optimized file does not exist: {optimized_path}")
            update_video_status(video_id, 'failed')
            return False

        os.remove(original_path)
        shutil.move(optimized_path, original_path)
        update_video_status(video_id, 'replaced')
        logger.info(f"[Replaced] {original_path}")
        return True

    except Exception as e:
        logger.error(f"[Error] Failed to replace {original_path}: {e}")
        update_video_status(video_id, 'failed')
        return False

def process_batch():
    videos = get_videos_by_status('accepted', REPLACE_BATCH_SIZE)
    if not videos:
        logger.info("No accepted videos to process.")
        return

    for video in videos:
        logger.info(f"Processing: {video['filename']}")
        replace_files(video["filepath"], video["optimized_path"], video["id"])

def remove_skipped_files():
    skipped_videos = get_videos_by_status('skipped')
    if not skipped_videos:
        logger.info("No skipped videos to remove.")
        return
    for video in skipped_videos:
        if os.path.exists(video["optimized_path"]):
            os.remove(video["optimized_path"])
            logger.info(f"[Removed] {video['optimized_path']}")

def main():
    logger.info("File replacer service started.")
    while True:
        try:
            process_batch()
            remove_skipped_files()
        except Exception as e:
            logger.error(f"[Fatal Error] {e}")
        time.sleep(REPLACE_INTERVAL)

if __name__ == "__main__":
    main()
