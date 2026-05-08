from typing import Optional

from fastapi import APIRouter, Query

from app.schemas import DashboardResponse
from app.services.reel_ingest import load_dashboard_status, load_reels, user_dashboard_paths
from app.services.library import is_demo_user, load_demo_dashboard_payload


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(user_id: Optional[str] = Query(default=None)):
    if is_demo_user(user_id):
        return DashboardResponse(**load_demo_dashboard_payload())
    try:
        return DashboardResponse(**load_dashboard_status(user_id=user_id))
    except Exception:
        normalized_user = user_id or "default"
        rows = load_reels(user_id=normalized_user)
        completed_count = len([row for row in rows if row.get("status") == "completed"])
        failed_count = len([row for row in rows if row.get("status") == "failed"])
        pending_count = len(rows) - completed_count - failed_count
        paths = user_dashboard_paths(normalized_user)
        return DashboardResponse(
            url_count=len(rows),
            processed_url_count=completed_count,
            pending_url_count=pending_count,
            failed_url_count=failed_count,
            running_job_count=0,
            queued_job_count=0,
            item_count=0,
            last_updated="",
            standard_page=paths["standard_page"],
            personalized_page=paths["personalized_page"],
            raw_output=paths["raw_output"],
            accumulated_output=paths["accumulated_output"],
            storage_mode="sqlite_with_csv_sync",
            media_mode="local_file_storage",
        )
