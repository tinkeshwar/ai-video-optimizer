import os
import sqlite3
import time
from contextlib import contextmanager
from backend.utils import logger
from typing import Optional
from threading import Lock

DB_PATH = os.getenv("DB_PATH", "/data/video_db.sqlite")
TIMEOUT = int(os.getenv("DB_TIMEOUT", "30"))  # Default 30 seconds timeout
MAX_RETRIES = int(os.getenv("DB_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.getenv("DB_RETRY_DELAY", "0.1"))  # 100ms default delay between retries

# Global lock for synchronizing database initialization
_init_lock = Lock()

def _configure_connection(conn: sqlite3.Connection) -> None:
    """Configure SQLite connection for optimal concurrency handling."""
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    # Set busy timeout to handle locked database
    conn.execute(f"PRAGMA busy_timeout={TIMEOUT * 1000}")  # Convert to milliseconds
    # Ensure foreign keys are enforced
    conn.execute("PRAGMA foreign_keys=ON")
    # Set synchronous mode to NORMAL for better performance while maintaining safety
    conn.execute("PRAGMA synchronous=NORMAL")
    # Row factory for dictionary-like access
    conn.row_factory = sqlite3.Row

@contextmanager
def get_db(retries: Optional[int] = None) -> sqlite3.Connection:
    """
    Enhanced context manager for database connection with retry logic and proper concurrency handling.
    
    Args:
        retries: Number of retries if database is locked. Defaults to MAX_RETRIES.
    
    Yields:
        sqlite3.Connection: Configured database connection
    """
    retries = MAX_RETRIES if retries is None else retries
    conn = None
    attempt = 0
    last_error = None

    while attempt <= retries:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=TIMEOUT)
            _configure_connection(conn)
            yield conn
            return
        except sqlite3.OperationalError as e:
            last_error = e
            if "database is locked" in str(e) and attempt < retries:
                logger.warning(f"Database locked, attempt {attempt + 1}/{retries}. Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                attempt += 1
                continue
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    logger.error(f"Error closing database connection: {e}")

    if last_error:
        raise last_error

def init_db():
    """
    Initializes the database with the required tables.
    Thread-safe implementation with proper error handling and retries.
    """
    # Use the global lock to ensure only one thread can initialize the database at a time
    with _init_lock:
        with get_db() as conn:
            cursor = conn.cursor()
            try:
                # Begin transaction
                cursor.execute("BEGIN EXCLUSIVE")

                # Create the table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS videos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT NOT NULL,
                        filepath TEXT NOT NULL,
                        ffprobe_data TEXT,
                        ai_command TEXT,
                        original_size INTEGER,
                        optimized_size INTEGER,
                        estimated_size INTEGER,
                        optimized_path TEXT,
                        original_codec TEXT,
                        new_codec TEXT,
                        status TEXT DEFAULT 'pending',
                        progress TEXT,
                        system_info TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Ensure the existing columns are added only once
                # Using a more robust approach to check for column existence
                def add_column_if_not_exists(table: str, column: str, type_: str):
                    columns = cursor.execute(f"PRAGMA table_info({table})").fetchall()
                    if not any(col[1] == column for col in columns):
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_}")

                add_column_if_not_exists("videos", "original_codec", "TEXT")
                add_column_if_not_exists("videos", "new_codec", "TEXT")
                add_column_if_not_exists("videos", "updated_at", "TEXT")
                add_column_if_not_exists("videos", "progress", "TEXT")
                add_column_if_not_exists("videos", "system_info", "TEXT")
                add_column_if_not_exists("videos", "estimated_size", "INTEGER")

                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_filepath ON videos(filepath)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON videos(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON videos(created_at)")

                # Create trigger to update updated_at timestamp
                cursor.execute('''
                    CREATE TRIGGER IF NOT EXISTS update_videos_timestamp 
                    AFTER UPDATE ON videos
                    BEGIN
                        UPDATE videos SET updated_at = CURRENT_TIMESTAMP 
                        WHERE id = NEW.id;
                    END;
                ''')

                # Commit changes to the database
                conn.commit()
                logger.info("Database initialized successfully with all required tables and indexes.")

            except sqlite3.DatabaseError as e:
                conn.rollback()
                logger.error(f"Database error during initialization: {e}")
                raise
            except Exception as e:
                conn.rollback()
                logger.error(f"Unexpected error during database initialization: {e}")
                raise
            finally:
                cursor.close()  # Ensure cursor is closed even in case of an error


