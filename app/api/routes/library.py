from fastapi import APIRouter, Query, Request

from app.schemas import LibraryResponse
from app.services.auth import ensure_user_access
from app.services.library import load_library_payload


router = APIRouter(prefix="/library", tags=["library"])


@router.get("", response_model=LibraryResponse)
def get_library(request: Request, user_id: str = Query(default="")):
    resolved_user_id = ensure_user_access(request, user_id, allow_demo=True)
    return LibraryResponse(**load_library_payload(resolved_user_id))
