import os
import sqlite3
import time

DB_PATH = os.getenv("DB_PATH", "/data/video_db.sqlite")
BATCH_SIZE = int(os.getenv("CONFIRM_BATCH_SIZE", 10))
CONFIRM_INTERVAL = int(os.getenv("CONFIRM_INTERVAL", 60))

AUTO_CONFIRMED = os.getenv("AUTO_CONFIRMED", "false").lower() == "true"
AUTO_ACCEPT = os.getenv("AUTO_ACCEPT", "false").lower() == "true"

def confirm_pending_videos():
    if not AUTO_CONFIRMED:
        print("AUTO_CONFIRMED is disabled. Skipping confirmation.")
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
            print("No pending videos to confirm.")
            return

        ids = [row[0] for row in rows]

        cursor.execute(f"""
            UPDATE videos
            SET status = 'confirmed'
            WHERE id IN ({','.join('?' for _ in ids)})
        """, ids)

        conn.commit()
        print(f"Confirmed {len(ids)} videos.")


def accept_optimized_videos():
    if not AUTO_ACCEPT:
        print("AUTO_ACCEPT is disabled. Skipping optimization acceptance.")
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

        print(f"Accepted {count} optimized videos.")

def main():
    print("Starting auto confirmer and accepter...")
    while True:
        try:
            confirm_pending_videos()
            accept_optimized_videos()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(CONFIRM_INTERVAL)

if __name__ == "__main__":
    main()
