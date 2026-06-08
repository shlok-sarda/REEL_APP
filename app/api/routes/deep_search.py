from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.config import settings
from app.services.auth import ensure_user_access, require_user
from app.services.deep_search import (
    MeiliClient,
    index_user_documents,
    load_deep_search_documents,
    search_documents_locally,
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
    backend: Literal["auto", "local", "meili"] = Query(default="auto"),
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

    if backend in {"auto", "meili"} and settings.meili_host:
        client = MeiliClient()
        try:
            result = client.search(settings.meili_index, query, user_id=resolved_user_id, limit=limit)
            return {
                "user_id": resolved_user_id,
                "query": query,
                "backend": "meili",
                "index": settings.meili_index,
                "result": result,
            }
        except Exception as exc:
            if backend == "meili":
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    documents = load_deep_search_documents(resolved_user_id)
    return {
        "user_id": resolved_user_id,
        "query": query,
        "backend": "local",
        "document_count": len(documents),
        "results": search_documents_locally(documents, query, limit=limit),
    }


@router.post("/index")
def index_deep_search(
    request: Request,
    user_id: str = Query(default=""),
    index: str = Query(default=""),
):
    require_user(request)
    resolved_user_id = ensure_user_access(request, user_id)
    if not settings.meili_host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MEILI_HOST is not configured. Configure a staging Meilisearch host before indexing.",
        )
    return index_user_documents(resolved_user_id, index_name=index or settings.meili_index)

