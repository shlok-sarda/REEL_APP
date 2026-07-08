import json
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from app.db.database import get_connection
from app.services.auth import current_user, ensure_user_access


router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/openai")
def openai_health(request: Request):
    """Have the server test its own OpenAI key and report the verdict.

    Splits "wrong key deployed" from "the key's account has no active billing":
    - key_fingerprint: compare against the key you pasted in Render env.
    - auth_check: does OpenAI accept the key at all (free call)?
    - billing_check: does OpenAI accept a paid call (1-token embedding)?
    """
    if not current_user(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in first")

    key = os.getenv("OPENAI_API_KEY", "").strip()
    info: dict[str, Any] = {
        "key_set": bool(key),
        "key_length": len(key),
        "key_fingerprint": f"{key[:6]}...{key[-4:]}" if len(key) > 14 else "(too short)",
    }
    if not key:
        info["auth_check"] = "skipped — no key in environment"
        info["billing_check"] = "skipped"
        return JSONResponse(info)

    from openai import OpenAI

    client = OpenAI(api_key=key, timeout=20, max_retries=0)
    try:
        client.models.list()
        info["auth_check"] = "ok — key is valid"
    except Exception as exc:
        info["auth_check"] = f"FAILED: {exc}"[:400]
    try:
        client.embeddings.create(model="text-embedding-3-small", input="ping")
        info["billing_check"] = "ok — OpenAI accepted a paid call, billing is active"
    except Exception as exc:
        info["billing_check"] = f"FAILED: {exc}"[:400]
    return JSONResponse(info)


def load_json(value: str, fallback: Any) -> Any:
    if not (value or "").strip():
        return fallback
    try:
        parsed = json.loads(value)
    except Exception:
        return fallback
    return parsed if parsed is not None else fallback


@router.get("/reels")
def get_recent_reel_diagnostics(request: Request, user_id: str = Query(default=""), limit: int = Query(default=10, ge=1, le=50)):
    resolved_user_id = ensure_user_access(request, user_id, allow_demo=True)
    if resolved_user_id == "demo":
        return []

    with get_connection() as connection:
        reel_rows = connection.execute(
            """
            SELECT id, user_id, url, shortcode, received_at, status, media_status,
                   local_video_path, thumbnail_path, source, created_at, updated_at
            FROM reels
            WHERE user_id = ?
            ORDER BY received_at DESC, created_at DESC
            LIMIT ?
            """,
            (resolved_user_id, limit),
        ).fetchall()
        reel_ids = [row["id"] for row in reel_rows]
        if not reel_ids:
            return []

        placeholders = ",".join("?" for _ in reel_ids)
        item_rows = connection.execute(
            f"""
            SELECT
                ri.id AS reel_item_id,
                ri.reel_id,
                ri.primary_category,
                ri.secondary_category,
                ri.item_name,
                ri.summary,
                ri.created_at AS item_created_at,
                rif.item_type,
                rif.canonical_domain,
                rif.canonical_subdomains_json,
                rif.canonical_entities_json,
                rif.canonical_location,
                rif.vibe_json,
                rif.intent,
                rif.audience_context,
                rif.confidence_scores_json,
                rif.interpretation_status,
                rif.interpretation_source,
                rif.metadata_json,
                rif.created_at AS feature_created_at,
                rif.updated_at AS feature_updated_at,
                pl.product_name,
                pl.brand,
                pl.model,
                pl.product_type,
                pl.search_query,
                pl.best_buy_link,
                pl.amazon_link,
                pl.flipkart_link,
                pl.nykaa_link
            FROM reel_items ri
            LEFT JOIN reel_item_features rif ON rif.reel_item_id = ri.id
            LEFT JOIN product_links pl ON pl.reel_item_id = ri.id
            WHERE ri.reel_id IN ({placeholders})
            ORDER BY ri.id ASC
            """,
            reel_ids,
        ).fetchall()

    items_by_reel: dict[str, list[dict[str, Any]]] = {}
    for row in item_rows:
        item = dict(row)
        item["canonical_subdomains"] = load_json(item.pop("canonical_subdomains_json", ""), [])
        item["canonical_entities"] = load_json(item.pop("canonical_entities_json", ""), [])
        item["vibe"] = load_json(item.pop("vibe_json", ""), [])
        item["confidence_scores"] = load_json(item.pop("confidence_scores_json", ""), {})
        item["metadata"] = load_json(item.pop("metadata_json", ""), {})
        items_by_reel.setdefault(item["reel_id"], []).append(item)

    diagnostics = []
    for row in reel_rows:
        reel = dict(row)
        items = items_by_reel.get(reel["id"], [])
        diagnostics.append(
            {
                **reel,
                "item_count": len(items),
                "feature_count": len([item for item in items if item.get("interpretation_status")]),
                "product_count": len([item for item in items if item.get("product_name") or item.get("best_buy_link")]),
                "items": items,
            }
        )
    return diagnostics
