import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "/data/video_db.sqlite")

@contextmanager
def get_db():
    """Context manager for database connection."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Ensures dictionary-like access to rows
        yield conn
    finally:
        if conn:
            conn.close()

def init_db():
    """Initializes the database with the required tables."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Create the table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT,
                    filepath TEXT,
                    ffprobe_data TEXT,
                    ai_command TEXT,
                    original_size INTEGER,
                    optimized_size INTEGER,
                    optimized_path TEXT,
                    original_codec TEXT,
                    new_codec TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Ensure the existing columns are added only once
            try:
                cursor.execute('ALTER TABLE videos ADD COLUMN original_codec TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute('ALTER TABLE videos ADD COLUMN new_codec TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Create an index on the filepath for faster lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_filepath ON videos(filepath)")

            # Commit changes to the database
            conn.commit()
            print("Database initialized successfully.")
        except sqlite3.DatabaseError as e:
            print(f"Database error during initialization: {e}")
        finally:
            cursor.close()  # Ensure cursor is closed even in case of an error
