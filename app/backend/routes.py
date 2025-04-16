from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.db import get_db

router = APIRouter()

class StatusUpdate(BaseModel):
    status: str

@router.get("/api/videos")
def get_all_videos():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos")
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="No videos found")
        conn.close()
        return [dict(row) for row in rows]

@router.get("/api/videos/{status}")
def get_specific_videos(status: str):
    with get_db() as conn:
        if status not in ["pending", "confirmed", "rejected", "ready", "optimized", "accepted", "skipped", "failed", "replaced"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE status = ?", (status,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

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
