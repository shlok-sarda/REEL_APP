from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas import ReelRecord
from app.services.jobs import enqueue_library_rebuild_job, enqueue_reel_job, start_worker_if_needed
from app.services.reel_ingest import delete_reel, get_reel_by_id, load_reels, reset_reel_for_retry


router = APIRouter(prefix="/reels", tags=["reels"])


@router.get("", response_model=list[ReelRecord])
def list_reels(user_id: Optional[str] = Query(default=None)):
    return load_reels(user_id=user_id)


@router.delete("/{reel_id}")
def remove_reel(reel_id: str):
    reel = get_reel_by_id(reel_id)
    if not reel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reel not found")
    deleted = delete_reel(reel_id)
    job = None
    if deleted:
        job = enqueue_library_rebuild_job(reel["user_id"])
        start_worker_if_needed()
    return {
        "ok": deleted,
        "deleted": reel_id,
        "user_id": reel["user_id"],
        "rebuild_job_status": job["status"] if job else "",
    }


@router.post("/{reel_id}/retry")
def retry_reel(reel_id: str):
    reel = get_reel_by_id(reel_id)
    if not reel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reel not found")
    reset = reset_reel_for_retry(reel_id)
    job = enqueue_reel_job(reel_id, user_id=reel["user_id"])
    start_worker_if_needed()
    return {
        "ok": True,
        "id": reel_id,
        "user_id": reel["user_id"],
        "status": reset["status"] if reset else "pending",
        "job_status": job["status"],
    }
