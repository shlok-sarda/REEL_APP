from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.services.auth import ensure_user_access, require_user
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

    try:
        return search_user_documents(resolved_user_id, query, limit=limit, backend=backend)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


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
