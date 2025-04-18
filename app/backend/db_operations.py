"""
Database operations module providing standardized access to the SQLite database
with proper concurrency handling.
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
import sqlite3
from contextlib import contextmanager
from .db import get_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %I:%M:%S %p")
logger = logging.getLogger(__name__)

class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass

def execute_with_retry(query: str, params: Tuple = None, retries: int = None) -> None:
    """
    Execute a database query with retry logic.
    
    Args:
        query: SQL query to execute
        params: Query parameters
        retries: Number of retries (None for default)
    """
    with get_db(retries=retries) as conn:
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database error executing query: {e}")
            raise DatabaseError(f"Failed to execute query: {e}")
        finally:
            cursor.close()

def fetch_one(query: str, params: Tuple = None, retries: int = None) -> Optional[Dict[str, Any]]:
    """
    Fetch a single row from the database.
    
    Args:
        query: SQL query to execute
        params: Query parameters
        retries: Number of retries (None for default)
    
    Returns:
        Dictionary containing row data or None if no row found
    """
    with get_db(retries=retries) as conn:
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Database error fetching row: {e}")
            raise DatabaseError(f"Failed to fetch row: {e}")
        finally:
            cursor.close()

def fetch_all(query: str, params: Tuple = None, retries: int = None) -> List[Dict[str, Any]]:
    """
    Fetch all rows from the database.
    
    Args:
        query: SQL query to execute
        params: Query parameters
        retries: Number of retries (None for default)
    
    Returns:
        List of dictionaries containing row data
    """
    with get_db(retries=retries) as conn:
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Database error fetching rows: {e}")
            raise DatabaseError(f"Failed to fetch rows: {e}")
        finally:
            cursor.close()

def insert_video(filepath: str, filename: str, metadata: str = None, codec: str = None, 
                size: int = None) -> int:
    """
    Insert a new video record into the database.
    
    Args:
        filepath: Path to the video file
        filename: Name of the video file
        metadata: FFprobe metadata (optional)
        codec: Video codec (optional)
        size: File size in bytes (optional)
    
    Returns:
        ID of the inserted record
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

def update_video_status(video_id: int, status: str, **kwargs) -> None:
    """
    Update video status and optional fields.
    
    Args:
        video_id: ID of the video record
        status: New status value
        **kwargs: Additional fields to update
    """
    fields = ["status = ?"]
    params = [status]
    
    for key, value in kwargs.items():
        fields.append(f"{key} = ?")
        params.append(value)
    
    query = f"UPDATE videos SET {', '.join(fields)} WHERE id = ?"
    params.append(video_id)
    
    execute_with_retry(query, tuple(params))

def get_video_by_path(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Get video record by filepath.
    
    Args:
        filepath: Path to the video file
    
    Returns:
        Dictionary containing video data or None if not found
    """
    return fetch_one("SELECT * FROM videos WHERE filepath = ?", (filepath,))

def get_pending_videos() -> List[Dict[str, Any]]:
    """
    Get all videos with 'pending' status.
    
    Returns:
        List of dictionaries containing video data
    """
    return fetch_all("SELECT * FROM videos WHERE status = 'pending' ORDER BY created_at ASC")

def get_processing_videos() -> List[Dict[str, Any]]:
    """
    Get all videos currently being processed.
    
    Returns:
        List of dictionaries containing video data
    """
    return fetch_all("SELECT * FROM videos WHERE status = 'processing' ORDER BY created_at ASC")

@contextmanager
def transaction(retries: int = None):
    """
    Context manager for database transactions with automatic rollback on error.
    
    Args:
        retries: Number of retries (None for default)
    """
    with get_db(retries=retries) as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

def get_confirmed_videos(limit: int) -> List[Dict[str, Any]]:
    """
    Get videos with 'confirmed' status, ordered by created_at.

    Args:
        limit: Maximum number of videos to return

    Returns:
        List of dictionaries containing video data
    """
    return fetch_all(
        "SELECT * FROM videos WHERE status = 'confirmed' ORDER BY created_at ASC LIMIT ?",
        (limit,)
    )

def update_video_command(video_id: int, ai_command: str) -> None:
    """
    Update video record with AI command.

    Args:
        video_id: ID of the video record
        ai_command: AI command to update
    """
    execute_with_retry(
        "UPDATE videos SET ai_command = ?, status = 'ready' WHERE id = ?",
        (ai_command, video_id)
    )

def get_accepted_records(limit: int) -> List[Dict[str, Any]]:
    """
    Get videos with 'accepted' status, ordered by created_at.

    Args:
        limit: Maximum number of videos to return

    Returns:
        List of dictionaries containing video data
    """
    return fetch_all(
        "SELECT * FROM videos WHERE status = 'accepted' ORDER BY created_at ASC LIMIT ?",
        (limit,)
    )


def update_record_status(video_id: int, status: str) -> None:
    """
    Update video record status.

    Args:
        video_id: ID of the video record
        status: New status value
    """
    execute_with_retry(
        "UPDATE videos SET status = ? WHERE id = ?",
        (status, video_id)
    )

def get_pending_videos(limit: int) -> List[Dict[str, Any]]:
    """
    Get videos with 'pending' status, ordered by created_at.

    Args:
        limit: Maximum number of videos to return

    Returns:
        List of dictionaries containing video data
    """
    return fetch_all(
        "SELECT * FROM videos WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
        (limit,)
    )

def get_optimized_videos(limit: int) -> List[Dict[str, Any]]:
    """
    Get videos with 'optimized' status, ordered by created_at.

    Args:
        limit: Maximum number of videos to return

    Returns:
        List of dictionaries containing video data
    """
    return fetch_all(
        "SELECT * FROM videos WHERE status = 'optimized' ORDER BY created_at ASC LIMIT ?",
        (limit,)
    )

def update_status_of_multiple_videos(video_ids: List[int], status: str) -> None:
    """
    Update the status of multiple videos.

    Args:
        video_ids: List of video IDs to update
        status: New status value
    """
    if not video_ids:
        return

    placeholders = ', '.join('?' for _ in video_ids)
    execute_with_retry(
        f"UPDATE videos SET status = ? WHERE id IN ({placeholders})",
        (status, *video_ids)
    )