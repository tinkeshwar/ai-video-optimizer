import os
import json
import time
from backend.utils import logger
from backend.db_operations import (
    get_videos_by_status,
    update_status_of_multiple_videos,
    update_video_stream_selection
)

BATCH_SIZE = int(os.getenv("CONFIRM_BATCH_SIZE", 10))
CONFIRM_INTERVAL = int(os.getenv("CONFIRM_INTERVAL", 60))

AUTO_CONFIRMED = os.getenv("AUTO_CONFIRMED", "false").lower() == "true"
AUTO_ACCEPT = os.getenv("AUTO_ACCEPT", "false").lower() == "true"

def confirm_pending_videos():
    if not AUTO_CONFIRMED:
        logger.info("Auto confirmation is disabled. Skipping confirmation.")
        return

    pending_videos = get_videos_by_status('pending', BATCH_SIZE)
    if not pending_videos:
        logger.info("No pending videos to confirm.")
        return

    confirmed = 0
    skipped = 0
    for v in pending_videos:
        audio = json.loads(v.get('audio_streams') or '[]')
        if len(audio) == 1:
            update_video_stream_selection(
                v['id'],
                selected_audio=json.dumps(audio[0]),
                selected_subtitle=None,
                comment='Auto confirmed (single audio stream)'
            )
            confirmed += 1
        else:
            skipped += 1

    if confirmed:
        logger.info(f"Auto confirmed {confirmed} single-audio videos.")
    if skipped:
        logger.info(f"Skipped {skipped} multi-audio videos (require manual selection).")



def accept_optimized_videos():
    if not AUTO_ACCEPT:
        logger.info("Auto acceptance is disabled. Skipping optimization acceptance.")
        return

    optimized_videos = get_videos_by_status('optimized', BATCH_SIZE)
    if not optimized_videos:
        logger.info("No optimized videos to accept.")
        return
    ids = [v["id"] for v in optimized_videos]

    comment = "Auto accepted"

    update_status_of_multiple_videos(ids, 'accepted', comment=comment)
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
