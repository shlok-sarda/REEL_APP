from fastapi import APIRouter

from app.config import settings
from app.schemas import HealthResponse
from app.services.reel_ingest import ensure_storage


router = APIRouter(tags=["health"])


def _queue_snapshot() -> dict:
    # Raw counts only — deliberately no janitor/recovery side effects here,
    # since health checks may be polled frequently.
    try:
        from app.db.database import get_connection

        with get_connection() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS n FROM processing_jobs GROUP BY status"
            ).fetchall()
        return {row["status"]: row["n"] for row in rows}
    except Exception:
        return {}


@router.get("/health", response_model=HealthResponse)
def health_check():
    ensure_storage()
    return HealthResponse(
        service="reel-organizer-api",
        endpoint="/instagram/webhook",
        environment=settings.app_env,
        storage_dir=str(settings.storage_dir),
        media_dir=str(settings.media_dir),
        csv_file=str(settings.reel_urls_csv),
        media_storage_mode="r2+local_cache" if settings.r2_enabled else "local_only",
        r2_enabled=settings.r2_enabled,
        queue=_queue_snapshot(),
    )
