"""
Database operations module providing standardized access to the SQLite database
with proper concurrency handling.
"""
from typing import Dict, List, Optional, Any, Tuple
import sqlite3
from contextlib import contextmanager
from backend.db import get_db
from backend.utils import logger
class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass

def execute_with_retry(query: str, params: Tuple = None, retries: int = None) -> None:
    """
    Execute a database query with retry logic.
    """
    with get_db(retries=retries) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params or ())
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database error executing query: {e}")
            raise DatabaseError(f"Failed to execute query: {e}")
        finally:
            cursor.close()

def fetch(query: str, params: Tuple = None, retries: int = None, fetch_one: bool = False) -> Any:
    """
    Fetch data from the database.
    """
    with get_db(retries=retries) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params or ())
            if fetch_one:
                row = cursor.fetchone()
                return dict(row) if row else None
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Database error fetching data: {e}")
            raise DatabaseError(f"Failed to fetch data: {e}")
        finally:
            cursor.close()

def insert_video(filepath: str, filename: str, metadata: str = None, codec: str = None, size: int = None) -> int:
    """
    Insert a new video record into the database.
    """
    query = """
        INSERT INTO videos (filepath, filename, ffprobe_data, original_codec, original_size)
        VALUES (?, ?, ?, ?, ?)
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, (filepath, filename, metadata, codec, size))
            video_id = cursor.lastrowid
            conn.commit()
            return video_id
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Failed to insert video record: {e}")
            raise DatabaseError(f"Failed to insert video: {e}")
        finally:
            cursor.close()

def get_video_by_path(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Get video record by filepath.
    """
    return fetch("SELECT * FROM videos WHERE filepath = ?", (filepath,), fetch_one=True)

def get_videos_by_status(status: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get videos by status, optionally limited by a maximum number.
    """
    query = f"SELECT * FROM videos WHERE status = ? ORDER BY created_at ASC"
    params = [status]
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    return fetch(query, tuple(params))


def get_next_ready_video() -> Optional[Dict[str, Any]]:
    """
    Fetch the next video ready for processing from the database.
    """
    return fetch("SELECT * FROM videos WHERE status = 'ready' ORDER BY created_at ASC LIMIT 1", fetch_one=True)

def update_video_command_and_system_info(video_id: int, ai_command: str, system_info: str) -> None:
    """
    Update video record with AI command.
    """
    execute_with_retry(
        "UPDATE videos SET ai_command = ?, system_info=?, status = 'ready', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (ai_command, system_info, video_id)
    )

def update_status_of_multiple_videos(video_ids: List[int], status: str) -> None:
    """
    Update the status of multiple videos.
    """
    if not video_ids:
        return
    placeholders = ', '.join('?' for _ in video_ids)
    execute_with_retry(
        f"UPDATE videos SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
        (status, *video_ids)
    )

def update_video_status(video_id: int, status: str, **kwargs) -> None:
    """
    Update video status and optional fields.
    """
    fields = ["status = ?"]
    params = [status]
    for key, value in kwargs.items():
        fields.append(f"{key} = ?")
        params.append(value)
    query = f"UPDATE videos SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
    params.append(video_id)
    execute_with_retry(query, tuple(params))

def update_video_progress(video_id: int, progress: str) -> None:
    """
    Update the progress of a video.
    """
    execute_with_retry("UPDATE videos SET progress = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (progress, video_id))

def update_video_estimated_size(video_id: int, estimated_size: int) -> None:
    """
    Update the estimated size of a video.
    """
    execute_with_retry("UPDATE videos SET estimated_size = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (estimated_size, video_id))

def update_final_output(video_id: int, output_path: str, codec: str, optimized_size: int,) -> None:
    """
    Update the final output path and codec of a video.
    """
    execute_with_retry("UPDATE videos SET optimized_size = ?, status = 'optimized', optimized_path = ?, new_codec = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",  (optimized_size, output_path, codec, video_id))

@contextmanager
def transaction(retries: int = None):
    """
    Context manager for database transactions with automatic rollback on error.
    """
    with get_db(retries=retries) as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
