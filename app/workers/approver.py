import os
import time
import logging
from backend.db_operations import (
    get_pending_videos,
    get_optimized_videos,
    update_status_of_multiple_videos
)

BATCH_SIZE = int(os.getenv("CONFIRM_BATCH_SIZE", 10))
CONFIRM_INTERVAL = int(os.getenv("CONFIRM_INTERVAL", 60))

AUTO_CONFIRMED = os.getenv("AUTO_CONFIRMED", "false").lower() == "true"
AUTO_ACCEPT = os.getenv("AUTO_ACCEPT", "false").lower() == "true"

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %I:%M:%S %p")
logger = logging.getLogger(__name__)

def confirm_pending_videos():
    if not AUTO_CONFIRMED:
        logger.info("Auto confirmation is disabled. Skipping confirmation.")
        return

    pending_videos = get_pending_videos(BATCH_SIZE)
    if not pending_videos:
        logger.info("No pending videos to confirm.")
        return
    
    ids = [row[0] for row in pending_videos]
    update_status_of_multiple_videos(ids, 'confirmed')
    logger.info(f"Confirmed {len(ids)} pending videos.")



def accept_optimized_videos():
    if not AUTO_ACCEPT:
        logger.info("Auto acceptance is disabled. Skipping optimization acceptance.")
        return

    optimized_videos = get_optimized_videos(BATCH_SIZE)
    if not optimized_videos:
        logger.info("No optimized videos to accept.")
        return
    ids = [row[0] for row in optimized_videos]
    update_status_of_multiple_videos(ids, 'accepted')
    logger.info(f"Accepted {len(ids)} optimized videos.")

def main():
    logger.info("Starting auto confirmation and acceptance...")
    while True:
        try:
            confirm_pending_videos()
            accept_optimized_videos()
        except Exception as e:
            logger.error(f"Error: {e}")
        time.sleep(CONFIRM_INTERVAL)

if __name__ == "__main__":
    main()
