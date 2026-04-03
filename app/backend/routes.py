from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.db import get_db

router = APIRouter()

class StatusUpdate(BaseModel):
    status: str

class BulkStatusUpdate(BaseModel):
    video_ids: list[int]
    status: str

class CommandUpdate(BaseModel):
    ai_command: str

VALID_STATUSES = [
    "pending", "confirmed", "rejected", "ready", "processing", "optimized",
    "accepted", "skipped", "failed", "replaced"
]

def execute_query(query, params=(), fetch_all=True):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if query.strip().lower().startswith(("update", "delete", "insert")):
            conn.commit()
            return cursor.rowcount
        return cursor.fetchall() if fetch_all else cursor.fetchone()


@router.get("/api/videos/status/count")
def get_status_counts():
    rows = execute_query(
        "SELECT status, COUNT(*) as count FROM videos GROUP BY status"
    )
    return {row['status']: row['count'] for row in rows}

@router.get("/api/videos/stats/summary")
def get_summary_stats():
    row = execute_query(
        """
        SELECT
            COUNT(*) as total_videos,
            COALESCE(SUM(original_size), 0) as total_original_size,
            COALESCE(SUM(CASE WHEN status = 'replaced' THEN optimized_size ELSE 0 END), 0) as total_optimized_size,
            COALESCE(SUM(CASE WHEN status = 'replaced' THEN original_size - optimized_size ELSE 0 END), 0) as total_saved,
            COUNT(CASE WHEN status = 'replaced' THEN 1 END) as completed_count,
            COUNT(CASE WHEN status IN ('ready', 'processing') THEN 1 END) as processing_count
        FROM videos
        """, fetch_all=False
    )
    return dict(row) if row else {}

@router.put("/api/videos/command/{video_id}")
def update_video_command(video_id: int, payload: CommandUpdate):
    command = payload.ai_command.strip()
    if not command.startswith("ffmpeg"):
        raise HTTPException(status_code=400, detail="Command must start with ffmpeg")
    
    rows_affected = execute_query(
        "UPDATE videos SET ai_command = ?, status = 'ready', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (command, video_id), fetch_all=False
    )
    if rows_affected == 0:
        raise HTTPException(status_code=404, detail="Video not found")
    
    execute_query(
        "INSERT INTO status_history (video_id, status, comment, created_at) VALUES (?, 'ready', 'Manual command edit', CURRENT_TIMESTAMP)",
        (video_id,)
    )
    return {"message": f"Command updated and video {video_id} queued for processing"}

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
def get_specific_videos(status: str, page: int = 1, limit: int = 10, codec: str = None, size: int = None, name: str = None, directory: str = None, sort_by: str = None, sort_order: str = 'asc'):
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
    
    total_count = execute_query(
        f"SELECT COUNT(*) as count FROM videos WHERE {where_clause}", params, fetch_all=False
    )['count']
    total_pages = max((total_count + limit - 1) // limit, 1)
    offset = (page - 1) * limit

    allowed_sort = {'filename', 'original_size', 'optimized_size', 'original_codec', 'created_at', 'updated_at'}
    order = f"ORDER BY {sort_by} {'DESC' if sort_order == 'desc' else 'ASC'}" if sort_by in allowed_sort else "ORDER BY created_at DESC"
    
    rows = execute_query(
        f"SELECT * FROM videos WHERE {where_clause} {order} LIMIT ? OFFSET ?", params + [limit, offset]
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
def update_status_bulk(payload: BulkStatusUpdate):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    if not payload.video_ids:
        raise HTTPException(status_code=400, detail="No video IDs provided")
    
    query = f"UPDATE videos SET status = ? WHERE id IN ({','.join(['?'] * len(payload.video_ids))})"
    params = [payload.status] + payload.video_ids
    rows_affected = execute_query(query, params, fetch_all=False)
    
    if rows_affected == 0:
        raise HTTPException(status_code=404, detail="No videos found for the provided IDs")
    
    comment = f"Bulk action: user changed status to {payload.status}"
    for vid in payload.video_ids:
        execute_query(
            "INSERT INTO status_history (video_id, status, comment, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (vid, payload.status, comment)
        )
    
    return {"message": f"Status updated to {payload.status} for {rows_affected} videos"}

@router.post("/api/videos/{video_id}/status")
def update_video_status(video_id: int, update: StatusUpdate):
    if update.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    rows_affected = execute_query(
        "UPDATE videos SET status = ? WHERE id = ?", (update.status, video_id), fetch_all=False
    )
    if rows_affected is None or rows_affected == 0:
        raise HTTPException(status_code=404, detail="Video not found")
    
    execute_query(
        "INSERT INTO status_history (video_id, status, comment, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)", (video_id, update.status, f"User changed status to {update.status}")
    )
    
    return {"message": f"Video {video_id} status updated to {update.status}"}

@router.delete("/api/videos/{video_id}")
def delete_video(video_id: int):
    rows_affected = execute_query(
        "DELETE FROM videos WHERE id = ?", (video_id,), fetch_all=False
    )
    if rows_affected == 0:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"message": f"Video {video_id} deleted successfully"}
