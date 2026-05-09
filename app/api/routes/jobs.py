from typing import Optional

from fastapi import APIRouter, Query, Request

from app.schemas import ProcessingJobRecord
from app.services.auth import ensure_user_access
from app.services.jobs import list_jobs


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[ProcessingJobRecord])
def get_jobs(request: Request, limit: int = Query(default=100, ge=1, le=500), user_id: Optional[str] = Query(default=None)):
    resolved_user_id = ensure_user_access(request, user_id or "", allow_demo=True)
    try:
        return list_jobs(limit=limit, user_id=resolved_user_id)
    except Exception:
        return []
