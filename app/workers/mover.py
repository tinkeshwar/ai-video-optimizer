
#!/usr/bin/env python3

import os
import shutil
from sqlite3 import connect, Row
import time

DB_PATH = os.getenv("DB_PATH", "/data/video_db.sqlite")

def get_db():
    conn = connect(DB_PATH)
    conn.row_factory = Row
    return conn

def get_accepted_records():
    with get_db() as conn:
      cursor = conn.cursor()
      cursor.execute("SELECT * FROM videos WHERE status = 'accepted'")
      videos = cursor.fetchall()
    return videos

def update_record_status(id, status):
    conn = get_db()
    with conn.cursor() as cursor:
      cursor.execute("UPDATE videos SET status = ? WHERE id = ?", (status, id))
    conn.commit()
    conn.close()

def replace_files(original_path, optimized_path, video_id):
    try:
      if not os.path.exists(original_path) or not os.path.exists(optimized_path):
        print(f"Missing files for: {original_path}")
      
      os.remove(original_path)
      shutil.move(optimized_path, original_path)
      update_record_status(video_id, 'replaced')
      print(f"Successfully replaced: {original_path}")
    except Exception as e:
      print(f"Error processing {original_path}: {str(e)}")
      update_record_status(video_id, 'failed')
      print(f"Failed to replace: {original_path}")
      return False
    return True
        
def main():
  print("Starting to move files...")
  while True:
    videos = get_accepted_records()
    for video in videos:
      print(f"Started moving: {video['filename']}")
      command = replace_files(video["filepath"], video["optimized_path"], video["id"])
      if command:
        print(f"Video replaced: {video['id']}")
    time.sleep(10)

if __name__ == "__main__":
  main()