import os
import time
import sqlite3
import subprocess

VIDEO_DIR = "/video-input"
DB_PATH = os.getenv("DB_PATH", "/data/video_db.sqlite")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 30))

VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov']

def get_video_files(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in VIDEO_EXTENSIONS):
                yield os.path.join(root, file)

def get_video_metadata(filepath):
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_format', '-show_streams',
            filepath  # Pass the raw filepath directly
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError("ffprobe is not installed or not available in PATH.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e.stderr}")

def file_already_exists(cursor, path):
    cursor.execute("SELECT 1 FROM videos WHERE filepath = ?", (path,))
    return cursor.fetchone() is not None

def scan_and_insert():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        for filepath in get_video_files(VIDEO_DIR):
            if not file_already_exists(cursor, filepath):
                print(f"New video found: {filepath}")
                filename = os.path.basename(filepath)
                metadata = get_video_metadata(filepath)
                filesize = os.path.getsize(filepath)

                cursor.execute('''
                    INSERT INTO videos (filename, filepath, ffprobe_data, status, original_size)
                    VALUES (?, ?, ?, 'pending', ?)
                ''', (filename, filepath, metadata, filesize))
                conn.commit()

if __name__ == "__main__":
    print("Starting directory scanner...")
    while True:
        scan_and_insert()
        time.sleep(SCAN_INTERVAL)
