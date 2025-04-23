from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.db import get_db

router = APIRouter()

class StatusUpdate(BaseModel):
    status: str

VALID_STATUSES = [
    "pending", "confirmed", "rejected", "ready", "optimized",
    "accepted", "skipped", "failed", "replaced"
]

def execute_query(query, params=(), fetch_all=True):
    """Helper function to execute a query and fetch results or affected rows."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if query.strip().lower().startswith(("update", "delete", "insert")):
            conn.commit()
            return cursor.rowcount
        return cursor.fetchall() if fetch_all else cursor.fetchone()


@router.get("/api/videos")
def get_all_videos(page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    rows = execute_query(
        "SELECT * FROM videos LIMIT ? OFFSET ?", (limit, offset)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No videos found")
    return [dict(row) for row in rows]

@router.get("/api/videos/{status}")
def get_specific_videos(status: str, page: int = 1, limit: int = 10, codec: str = None, size: int = None, name: str = None, directory: str = None):
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    filters = ["status = ?"]
    params = [status]
    
    if codec:
        filters.append("original_codec = ?")
        params.append(codec)
    if size:
        filters.append("original_size >= ?")
        params.append(size)
    if name:
        filters.append("filename LIKE ?")
        params.append(f"%{name}%")
    if directory:
        filters.append("filepath LIKE ?")
        params.append(f"%{directory}%")
    
    where_clause = " AND ".join(filters)
    
    # Get total count for pagination
    total_count = execute_query(
        f"SELECT COUNT(*) as count FROM videos WHERE {where_clause}", params, fetch_all=False
    )['count']
    total_pages = (total_count + limit - 1) // limit
    offset = (page - 1) * limit
    
    rows = execute_query(
        f"SELECT * FROM videos WHERE {where_clause} LIMIT ? OFFSET ?", params + [limit, offset]
    )
    
    videos = []
    for row in rows:
        video = dict(row)
        history = execute_query(
            "SELECT * FROM status_history WHERE video_id = ? ORDER BY created_at ASC", (video['id'],)
        )
        video['history'] = [dict(h) for h in history]
        videos.append(video)
    
    return {
        "list": videos,
        "page": page,
        "total_pages": total_pages,
        "requested_per_page": limit
    }

@router.post("/api/videos/status")
def update_status_bulk(video_ids: list[int], update: StatusUpdate):
    if update.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    if not video_ids:
        raise HTTPException(status_code=400, detail="No video IDs provided")
    
    # Update the status for all provided video IDs
    query = f"UPDATE videos SET status = ? WHERE id IN ({','.join(['?'] * len(video_ids))})"
    params = [update.status] + video_ids
    rows_affected = execute_query(query, params, fetch_all=False)
    
    if rows_affected == 0:
        raise HTTPException(status_code=404, detail="No videos found for the provided IDs")
    
    # Update the status history for each video
    for video_id in video_ids:
        execute_query(
            "INSERT INTO status_history (video_id, status, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (video_id, update.status)
        )
    
    return {"message": f"Status updated to {update.status} for {rows_affected} videos"}

@router.post("/api/videos/{video_id}/status")
def update_video_status(video_id: int, update: StatusUpdate):
    if update.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    rows_affected = execute_query(
        "UPDATE videos SET status = ? WHERE id = ?", (update.status, video_id), fetch_all=False
    )
    if rows_affected is None or rows_affected == 0:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Update the status history
    execute_query(
        "INSERT INTO status_history (video_id, status, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (video_id, update.status)
    )
    
    return {"message": f"Video {video_id} status updated to {update.status}"}

@router.get("/api/videos/status/count")
def get_status_counts():
    rows = execute_query(
        "SELECT status, COUNT(*) as count FROM videos GROUP BY status"
    )
    return {row['status']: row['count'] for row in rows}

@router.delete("/api/videos/{video_id}")
def delete_video(video_id: int):
    rows_affected = execute_query(
        "DELETE FROM videos WHERE id = ?", (video_id,), fetch_all=False
    )
    if rows_affected == 0:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"message": f"Video {video_id} deleted successfully"}
