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
    Insert a new video record into the database and log the status as 'pending' in status_history.
    """
    query = """
        INSERT INTO videos (filepath, filename, ffprobe_data, original_codec, original_size)
        VALUES (?, ?, ?, ?, ?)
    """
    with transaction() as conn:
        cursor = conn.cursor()
        try:
            # Insert the video record
            cursor.execute(query, (filepath, filename, metadata, codec, size))
            video_id = cursor.lastrowid
            # Log the initial status as 'pending' in status_history
            cursor.execute(
                "INSERT INTO status_history (video_id, status, created_at) VALUES (?, 'pending', CURRENT_TIMESTAMP)",
                (video_id,)
            )
            return video_id
        except sqlite3.Error as e:
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
    Update video record with AI command and system info, and log the status change in status_history.
    """
    with transaction() as conn:
        cursor = conn.cursor()
        try:
            # Update the video record
            cursor.execute(
                "UPDATE videos SET ai_command = ?, system_info = ?, status = 'ready', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (ai_command, system_info, video_id)
            )
            # Insert status change into status_history
            cursor.execute(
                "INSERT INTO status_history (video_id, status, created_at) VALUES (?, 'ready', CURRENT_TIMESTAMP)",
                (video_id,)
            )
        except sqlite3.Error as e:
            logger.error(f"Failed to update video command and system info: {e}")
            raise DatabaseError(f"Failed to update video command and system info: {e}")
        finally:
            cursor.close()

def update_status_of_multiple_videos(video_ids: List[int], status: str) -> None:
    """
    Update the status of multiple videos and log the status change in status_history.
    """
    if not video_ids:
        return
    placeholders = ', '.join('?' for _ in video_ids)
    with transaction() as conn:
        cursor = conn.cursor()
        try:
            # Update the status of videos
            cursor.execute(
                f"UPDATE videos SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                (status, *video_ids)
            )
            # Insert status changes into status_history
            for video_id in video_ids:
                cursor.execute(
                    "INSERT INTO status_history (video_id, status, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (video_id, status)
                )
        except sqlite3.Error as e:
            logger.error(f"Failed to update status of multiple videos: {e}")
            raise DatabaseError(f"Failed to update status of multiple videos: {e}")
        finally:
            cursor.close()

def update_video_status(video_id: int, status: str, **kwargs) -> None:
    """
    Update video status, optional fields, and log the status change in status_history.
    """
    fields = ["status = ?"]
    params = [status]
    for key, value in kwargs.items():
        fields.append(f"{key} = ?")
        params.append(value)
    query = f"UPDATE videos SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
    params.append(video_id)
    with transaction() as conn:
        cursor = conn.cursor()
        try:
            # Update the video record
            cursor.execute(query, tuple(params))
            # Insert status change into status_history
            cursor.execute(
                "INSERT INTO status_history (video_id, status, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (video_id, status)
            )
        except sqlite3.Error as e:
            logger.error(f"Failed to update video status: {e}")
            raise DatabaseError(f"Failed to update video status: {e}")
        finally:
            cursor.close()

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

def update_final_output(video_id: int, output_path: str, codec: str, optimized_size: int) -> None:
    """
    Update the final output path and codec of a video and log the status change in status_history.
    """
    with transaction() as conn:
        cursor = conn.cursor()
        try:
            # Update the video record
            cursor.execute(
                "UPDATE videos SET optimized_size = ?, status = 'optimized', optimized_path = ?, new_codec = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (optimized_size, output_path, codec, video_id)
            )
            # Insert status change into status_history
            cursor.execute(
                "INSERT INTO status_history (video_id, status, created_at) VALUES (?, 'optimized', CURRENT_TIMESTAMP)",
                (video_id,)
            )
        except sqlite3.Error as e:
            logger.error(f"Failed to update final output: {e}")
            raise DatabaseError(f"Failed to update final output: {e}")
        finally:
            cursor.close()

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
