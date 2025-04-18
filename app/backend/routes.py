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
    """Helper function to execute a query and fetch results."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall() if fetch_all else cursor.fetchone()
        conn.close()
        return result

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
def get_specific_videos(status: str, page: int = 1, limit: int = 10, codec: str = None, size: int = None):
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
    
    return {
        "list": [dict(row) for row in rows],
        "page": page,
        "total_pages": total_pages,
        "requested_per_page": limit
    }

@router.post("/api/videos/{video_id}/status")
def update_video_status(video_id: int, update: StatusUpdate):
    rows_affected = execute_query(
        "UPDATE videos SET status = ? WHERE id = ?", (update.status, video_id), fetch_all=False
    )
    if rows_affected == 0:
        raise HTTPException(status_code=404, detail="Video not found")
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
