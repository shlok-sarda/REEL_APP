from typing import Optional

from fastapi import APIRouter, Query

from app.schemas import DashboardResponse
from app.services.reel_ingest import load_dashboard_status


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(user_id: Optional[str] = Query(default=None)):
    return DashboardResponse(**load_dashboard_status(user_id=user_id))
