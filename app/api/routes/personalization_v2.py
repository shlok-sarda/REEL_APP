from fastapi import APIRouter, Query, Request

from app.services.auth import ensure_user_access
from app.services.personalization_v2.engine import PersonalizationV2Engine
from app.services.personalization_v2.repository import PersonalizationV2Repository


router = APIRouter(prefix="/personalization-v2", tags=["personalization-v2"])


@router.get("/debug")
def get_personalization_v2_debug(request: Request, user_id: str = Query(default="")):
    resolved_user_id = ensure_user_access(request, user_id, allow_demo=False)
    repo = PersonalizationV2Repository()
    return repo.load_debug_snapshot(resolved_user_id)


@router.post("/rebuild")
def rebuild_personalization_v2(request: Request, user_id: str = Query(default="")):
    resolved_user_id = ensure_user_access(request, user_id, allow_demo=False)
    engine = PersonalizationV2Engine()
    snapshot = engine.backfill_user(resolved_user_id, use_llm=False, use_remote_embeddings=False)
    return {
        "ok": True,
        "user_id": resolved_user_id,
        "feature_count": snapshot["feature_count"],
        "node_count": snapshot["node_count"],
        "membership_count": snapshot["membership_count"],
        "title_count": snapshot["title_count"],
    }
