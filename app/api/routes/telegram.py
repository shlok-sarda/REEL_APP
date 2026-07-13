from app.config import settings
from fastapi import APIRouter, Header, HTTPException, status

from app.schemas import TelegramIngestRequest, TelegramIngestResponse
from app.services.auth import get_user_by_telegram_user_id
from app.services.jobs import enqueue_reel_job, ensure_background_progress
from app.services.reel_ingest import append_reel, is_valid_instagram_url


router = APIRouter(tags=["telegram"])


@router.post("/telegram-ingest", response_model=TelegramIngestResponse)
def telegram_ingest(payload: TelegramIngestRequest, x_ingest_token: str = Header(default="")):
    if settings.telegram_ingest_secret and x_ingest_token.strip() != settings.telegram_ingest_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ingest token",
        )

    if not is_valid_instagram_url(payload.url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Instagram reel/post URL",
        )

    resolved_user_id = (payload.user_id or "").strip()
    if not resolved_user_id and payload.telegram_user_id:
        user = get_user_by_telegram_user_id(payload.telegram_user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Telegram account not linked. Please sign in on the website and connect Telegram first.",
            )
        resolved_user_id = user["id"]

    reel = append_reel(payload.url, user_id=resolved_user_id or "default", source=payload.source or "telegram")
    job = enqueue_reel_job(reel["id"], user_id=reel["user_id"])
    ensure_background_progress()
    return TelegramIngestResponse(
        id=reel["id"],
        user_id=reel["user_id"],
        url=reel["url"],
        status=reel["status"],
        job_status=job["status"],
        saved_to=str(settings.reel_urls_csv),
    )
