import os
import sqlite3
import time
import logging

DB_PATH = os.getenv("DB_PATH", "/data/video_db.sqlite")
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

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id FROM videos
            WHERE status = 'pending'
            LIMIT ?
        """, (BATCH_SIZE,))
        
        rows = cursor.fetchall()
        if not rows:
            logger.info("No pending videos to confirm.")
            return

        ids = [row[0] for row in rows]

        cursor.execute(f"""
            UPDATE videos
            SET status = 'confirmed'
            WHERE id IN ({','.join('?' for _ in ids)})
        """, ids)

        conn.commit()
        logger.info(f"Confirmed {len(ids)} videos.")


def accept_optimized_videos():
    if not AUTO_ACCEPT:
        logger.info("Auto acceptance is disabled. Skipping optimization acceptance.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE videos
            SET status = 'accepted'
            WHERE status = 'optimized'
        """)

        count = cursor.rowcount
        conn.commit()

        logger.info(f"Accepted {count} optimized videos.")

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
