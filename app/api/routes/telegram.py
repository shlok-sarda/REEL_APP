from app.config import settings
from fastapi import APIRouter, HTTPException, status

from app.schemas import TelegramIngestRequest, TelegramIngestResponse
from app.services.jobs import enqueue_reel_job, start_worker_if_needed
from app.services.reel_ingest import append_reel, is_valid_instagram_url


router = APIRouter(tags=["telegram"])


@router.post("/telegram-ingest", response_model=TelegramIngestResponse)
def telegram_ingest(payload: TelegramIngestRequest):
    if not is_valid_instagram_url(payload.url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Instagram reel/post URL",
        )

    reel = append_reel(payload.url, user_id=payload.user_id or "default")
    job = enqueue_reel_job(reel["id"], user_id=reel["user_id"])
    start_worker_if_needed()
    return TelegramIngestResponse(
        id=reel["id"],
        user_id=reel["user_id"],
        url=reel["url"],
        status=reel["status"],
        job_status=job["status"],
        saved_to=str(settings.reel_urls_csv),
    )
