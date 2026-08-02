from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse

from app.schemas import LibraryResponse
from app.services.auth import block_demo_link_writes, ensure_user_access
from app.services.collections import (
    reel_cards_export,
    reel_sheet,
    reel_sheet_csv,
    rebuild_estimate,
    start_shelf_rebuild,
)
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


@router.get("/sheet", response_class=PlainTextResponse)
def get_reel_sheet(request: Request, user_id: str = Query(default=""), format: str = Query(default="text")):
    """Every reel as a list to hand-label.

    format=csv downloads a file that opens in Excel with real columns; the
    default renders readable in a browser tab.
    """
    resolved_user_id = ensure_user_access(request, user_id, allow_demo=False)
    if format.lower() == "cards":
        return PlainTextResponse(
            reel_cards_export(resolved_user_id),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="clipnest_cards.json"'},
        )
    if format.lower() == "csv":
        return PlainTextResponse(
            reel_sheet_csv(resolved_user_id),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="clipnest_answer_sheet.csv"'},
        )
    return reel_sheet(resolved_user_id)


@router.get("/rebuild-cost")
def get_rebuild_cost(request: Request, user_id: str = Query(default="")):
    """What a rebuild would cost for this account. Calls nothing, spends nothing."""
    resolved_user_id = ensure_user_access(request, user_id, allow_demo=False)
    return rebuild_estimate(resolved_user_id)


@router.post("/rebuild")
def post_library_rebuild(request: Request, user_id: str = Query(default="")):
    """Rebuild the Collections shelves on a background thread.

    Returns immediately — no LLM call happens on the request thread. This
    bypasses the job queue on purpose: a rebuild_library job runs the legacy
    processor first, which times out at 600s on a real library and takes the
    shelves down with it.
    """
    resolved_user_id = ensure_user_access(request, user_id, allow_demo=False)
    block_demo_link_writes(request, "rebuild collections")
    return start_shelf_rebuild(resolved_user_id)
