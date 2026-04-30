from typing import Optional

from fastapi import APIRouter, Query

from app.schemas import DashboardResponse
from app.services.reel_ingest import load_dashboard_status
from app.services.library import is_demo_user, load_demo_dashboard_payload


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(user_id: Optional[str] = Query(default=None)):
    if is_demo_user(user_id):
        return DashboardResponse(**load_demo_dashboard_payload())
    return DashboardResponse(**load_dashboard_status(user_id=user_id))
