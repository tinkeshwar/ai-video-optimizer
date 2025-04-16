#!/usr/bin/env python3

import os
import shutil
import time
import sqlite3
from sqlite3 import Row

DB_PATH = os.getenv("DB_PATH", "/data/video_db.sqlite")
REPLACE_BATCH_SIZE = int(os.getenv("REPLACE_BATCH_SIZE", 5))  # Default batch size
REPLACE_INTERVAL = int(os.getenv("REPLACE_INTERVAL", 10))     # Sleep between batches

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = Row
    return conn

def get_accepted_records(limit: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM videos WHERE status = 'accepted' LIMIT ?",
            (limit,)
        )
        return cursor.fetchall()

def update_record_status(video_id: int, status: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE videos SET status = ? WHERE id = ?",
            (status, video_id)
        )
        conn.commit()

def replace_files(original_path: str, optimized_path: str, video_id: int) -> bool:
    try:
        if not os.path.exists(original_path):
            print(f"[Missing] Original file does not exist: {original_path}")
            update_record_status(video_id, 'failed')
            return False

        if not os.path.exists(optimized_path):
            print(f"[Missing] Optimized file does not exist: {optimized_path}")
            update_record_status(video_id, 'failed')
            return False

        os.remove(original_path)
        shutil.move(optimized_path, original_path)
        update_record_status(video_id, 'replaced')
        print(f"[Replaced] {original_path}")
        return True

    except Exception as e:
        print(f"[Error] Failed to replace {original_path}: {e}")
        update_record_status(video_id, 'failed')
        return False

def process_batch():
    videos = get_accepted_records(REPLACE_BATCH_SIZE)
    if not videos:
        print("No accepted videos to process.")
        return

    for video in videos:
        print(f"Processing: {video['filename']}")
        replace_files(video["filepath"], video["optimized_path"], video["id"])

def main():
    print("File replacer service started.")
    while True:
        try:
            process_batch()
        except Exception as e:
            print(f"[Fatal Error] {e}")
        time.sleep(REPLACE_INTERVAL)

if __name__ == "__main__":
    main()
