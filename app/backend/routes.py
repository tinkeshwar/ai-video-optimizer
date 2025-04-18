from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.db import get_db

router = APIRouter()

class StatusUpdate(BaseModel):
    status: str

@router.get("/api/videos")
def get_all_videos(page: int = 1, limit: int = 10):
    with get_db() as conn:
        cursor = conn.cursor()
        offset = (page - 1) * limit
        cursor.execute("SELECT * FROM videos LIMIT ? OFFSET ?", (limit, offset))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="No videos found")
        conn.close()
        return [dict(row) for row in rows]

@router.get("/api/videos/{status}")
def get_specific_videos(status: str, page: int = 1, limit: int = 10, codec: str = None):
    with get_db() as conn:
        if status not in ["pending", "confirmed", "rejected", "ready", "optimized", "accepted", "skipped", "failed", "replaced"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        cursor = conn.cursor()
        
        # Get total count for pagination
        if codec:
            cursor.execute("SELECT COUNT(*) as count FROM videos WHERE status = ? AND codec = ?", 
                         (status, codec))
        else:
            cursor.execute("SELECT COUNT(*) as count FROM videos WHERE status = ?", 
                         (status,))
        total_count = cursor.fetchone()['count']
        total_pages = (total_count + limit - 1) // limit
        
        offset = (page - 1) * limit
        
        if codec:
            cursor.execute("SELECT * FROM videos WHERE status = ? AND codec = ? LIMIT ? OFFSET ?", 
                         (status, codec, limit, offset))
        else:
            cursor.execute("SELECT * FROM videos WHERE status = ? LIMIT ? OFFSET ?", 
                         (status, limit, offset))
            
        rows = cursor.fetchall()
        conn.close()
        return {
            "list": [dict(row) for row in rows],
            "page": page,
            "total_pages": total_pages,
            "requested_per_page": limit
        }
    

@router.post("/api/videos/{video_id}/status")
def update_video_status(video_id: int, update: StatusUpdate):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE videos SET status = ? WHERE id = ?", (update.status, video_id))
        conn.commit()
        conn.close()
        return {"message": f"Video {video_id} status updated to {update.status}"}

@router.get("/api/videos/status/count")
def get_status_counts():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, COUNT(*) as count FROM videos GROUP BY status")
        rows = cursor.fetchall()
        conn.close()
        return {row['status']: row['count'] for row in rows}
    
@router.delete("/api/videos/{video_id}")
def delete_video(video_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Video not found")
        conn.close()
        return {"message": f"Video {video_id} deleted successfully"}
