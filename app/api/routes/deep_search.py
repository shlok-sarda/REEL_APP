import time
from typing import Literal, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request, status

from app.services.auth import ensure_user_access, is_demo_link_session, require_admin, require_user
from app.services.deep_search import (
    backfill_reel_visual_search,
    build_search_collection_candidates,
    evaluate_user_search,
    explain_user_search,
    index_user_documents,
    load_deep_search_documents,
    rebuild_deep_search_documents,
    search_user_documents,
)
from app.services.search_log import log_click, log_search, recent_searches


router = APIRouter(prefix="/deep-search", tags=["deep-search"])


@router.get("/documents")
def deep_search_documents(
    request: Request,
    user_id: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=500),
):
    resolved_user_id = ensure_user_access(request, user_id)
    documents = load_deep_search_documents(resolved_user_id)
    return {
        "user_id": resolved_user_id,
        "document_count": len(documents),
        "documents": documents[:limit],
    }


def _card(document: dict) -> dict:
    """The slice of a search document the app UI shows (creator, places named
    in the reel, on-screen text) without transcripts or match context."""
    def head(value, n):
        return list(value or [])[:n] if isinstance(value, list) else []

    items = []
    for item in head(document.get("items"), 30):
        if not isinstance(item, dict):
            continue
        items.append({
            "item_name": item.get("item_name") or item.get("name") or "",
            "summary": str(item.get("summary") or item.get("item_summary") or "")[:220],
            "item_type": item.get("item_type") or "",
            "location": item.get("canonical_location") or item.get("location") or "",
        })
    return {
        "reel_id": document.get("reel_id"),
        "creator": document.get("creator") or "",
        "main_subject": document.get("main_subject") or "",
        "primary_category": document.get("primary_category") or "",
        "secondary_category": document.get("secondary_category") or "",
        "locations": head(document.get("locations"), 6),
        "item_names": head(document.get("item_names"), 30),
        "visible_text": head(document.get("visible_text"), 10),
        "visual_entities": head(document.get("visual_entities"), 10),
        "visual_summary": str(document.get("visual_summary") or "")[:400],
        "caption": str(document.get("caption") or "")[:300],
        "transcript_excerpt": str(document.get("transcript") or "")[:300],
        "items": items,
    }


@router.get("/cards")
def deep_search_cards(request: Request, user_id: str = Query(default="")):
    resolved_user_id = ensure_user_access(request, user_id)
    documents = load_deep_search_documents(resolved_user_id)
    return {"user_id": resolved_user_id, "documents": [_card(d) for d in documents if d.get("reel_id")]}


@router.get("")
def deep_search(
    request: Request,
    q: str = Query(default=""),
    user_id: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=100),
    backend: Literal["auto", "hybrid", "local", "meili"] = Query(default="auto"),
):
    resolved_user_id = ensure_user_access(request, user_id)
    query = q.strip()
    if not query:
        return {
            "user_id": resolved_user_id,
            "query": query,
            "backend": "none",
            "results": [],
        }

    started = time.monotonic()
    try:
        payload = search_user_documents(resolved_user_id, query, limit=limit, backend=backend)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    try:
        if isinstance(payload, dict) and not is_demo_link_session(request):
            latency_ms = int((time.monotonic() - started) * 1000)
            payload["query_id"] = log_search(resolved_user_id, query, payload, latency_ms)
    except Exception:
        pass
    return payload


@router.post("/click")
def deep_search_click(request: Request, payload: dict = Body(default={})):
    """Fire-and-forget beacon: a search result was opened. Always 200."""
    try:
        user_id = ensure_user_access(request, str(payload.get("user_id", "")))
        if not is_demo_link_session(request):
            log_click(user_id, payload.get("query_id"), str(payload.get("query", "")),
                      str(payload.get("reel_id", "")), payload.get("position"))
    except Exception:
        pass
    return {"ok": True}


@router.get("/log")
def deep_search_log(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=500, ge=1, le=5000),
):
    require_admin(request)
    return recent_searches(days, limit)


@router.get("/evaluate")
def evaluate_deep_search(
    request: Request,
    user_id: str = Query(default=""),
    q: Optional[list[str]] = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
):
    resolved_user_id = ensure_user_access(request, user_id)
    return evaluate_user_search(resolved_user_id, queries=q or None, limit=limit)


@router.get("/explain")
def explain_deep_search(
    request: Request,
    q: str = Query(default=""),
    user_id: str = Query(default=""),
    limit: int = Query(default=10, ge=1, le=50),
):
    resolved_user_id = ensure_user_access(request, user_id)
    return explain_user_search(resolved_user_id, q.strip(), limit=limit)


@router.get("/collections")
def deep_search_collections(
    request: Request,
    q: str = Query(default=""),
    user_id: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=100),
):
    resolved_user_id = ensure_user_access(request, user_id)
    return build_search_collection_candidates(resolved_user_id, q.strip(), limit=limit)


@router.post("/index")
def index_deep_search(
    request: Request,
    user_id: str = Query(default=""),
    index: str = Query(default=""),
):
    require_user(request)
    resolved_user_id = ensure_user_access(request, user_id)
    from app.config import settings

    if not settings.meili_host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MEILI_HOST is not configured. Configure a staging Meilisearch host before indexing.",
        )
    return index_user_documents(resolved_user_id, index_name=index or settings.meili_index)


@router.post("/rebuild-documents")
def rebuild_deep_search(
    request: Request,
    user_id: str = Query(default=""),
):
    require_user(request)
    resolved_user_id = ensure_user_access(request, user_id)
    return rebuild_deep_search_documents(resolved_user_id)


@router.post("/backfill-visual")
def backfill_visual_deep_search(
    request: Request,
    user_id: str = Query(default=""),
    reel_id: str = Query(default=""),
    url: str = Query(default=""),
    shortcode: str = Query(default=""),
):
    require_user(request)
    resolved_user_id = ensure_user_access(request, user_id)
    payload = backfill_reel_visual_search(
        resolved_user_id,
        reel_id=reel_id,
        url=url,
        shortcode=shortcode,
    )
    if not payload.get("ok"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=payload)
    return payload
