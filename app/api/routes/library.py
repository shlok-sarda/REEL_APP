from fastapi import APIRouter, Query, Request

from app.schemas import LibraryResponse
from app.services.auth import block_demo_link_writes, ensure_user_access
from app.services.jobs import enqueue_library_rebuild_job
from app.services.library import collections_status, load_library_payload


router = APIRouter(prefix="/library", tags=["library"])


@router.get("", response_model=LibraryResponse)
def get_library(request: Request, user_id: str = Query(default="")):
    resolved_user_id = ensure_user_access(request, user_id, allow_demo=True)
    return LibraryResponse(**load_library_payload(resolved_user_id))


@router.get("/status")
def get_library_status(request: Request, user_id: str = Query(default="")):
    """Self-diagnosis for the Collections rollout — open it in a browser."""
    resolved_user_id = ensure_user_access(request, user_id, allow_demo=True)
    return collections_status(resolved_user_id)


@router.post("/rebuild")
def post_library_rebuild(request: Request, user_id: str = Query(default="")):
    """Queue a shelf rebuild. The routing itself happens in the worker, never here."""
    resolved_user_id = ensure_user_access(request, user_id, allow_demo=False)
    block_demo_link_writes(request, "rebuild collections")
    return enqueue_library_rebuild_job(resolved_user_id)
