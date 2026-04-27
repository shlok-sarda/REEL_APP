from typing import Optional

from fastapi import APIRouter, Query

from app.schemas import ProcessingJobRecord
from app.services.jobs import list_jobs


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[ProcessingJobRecord])
def get_jobs(limit: int = Query(default=100, ge=1, le=500), user_id: Optional[str] = Query(default=None)):
    return list_jobs(limit=limit, user_id=user_id)
