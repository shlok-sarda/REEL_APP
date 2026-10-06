"""Discover data APIs: reel-map pins, per-reel recipe cards, search reports.

No standalone pages here — the map is a full-screen overlay INSIDE the main
app (users install the web app to their home screen, so everything must stay
on one URL), and recipes are per-reel actions in the reel sheet.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.services.auth import block_link_session_writes, ensure_user_access, is_demo_link_session
from app.services.discover import (
    build_map_pins,
    build_recipes,
    extract_reel_recipe,
    recipes_enabled,
    reel_recipe_status,
)
from app.services.library import is_demo_user
from app.services.search_report import ReportError, build_search_report, report_events, search_report_enabled

router = APIRouter(tags=["discover"])


@router.get("/api/map-data")
def map_data(request: Request, user_id: str = Query(default="")):
    if user_id and is_demo_user(user_id):
        return {"pins": [], "pending_places": 0}
    resolved = ensure_user_access(request, user_id)
    return build_map_pins(resolved)


@router.get("/api/reel-recipe")
def reel_recipe(request: Request, reel_id: str = Query(default=""), user_id: str = Query(default="")):
    if not reel_id:
        raise HTTPException(status_code=400, detail="reel_id required")
    if user_id and is_demo_user(user_id):
        return {"status": "none"}
    resolved = ensure_user_access(request, user_id)
    return reel_recipe_status(resolved, reel_id)


@router.post("/api/reel-recipe/extract")
def reel_recipe_extract(request: Request, payload: dict = Body(...)):
    reel_id = str(payload.get("reel_id", ""))
    if not reel_id:
        raise HTTPException(status_code=400, detail="reel_id required")
    user_id = str(payload.get("user_id", ""))
    if user_id and is_demo_user(user_id):
        return {"status": "none"}
    # extraction spends OpenAI credit — shared demo-link sessions can't trigger it
    block_link_session_writes(request, "extract recipes")
    resolved = ensure_user_access(request, user_id)
    return extract_reel_recipe(resolved, reel_id)


def _report_request(request: Request, payload: dict) -> tuple[str, str, list[str], list[str]]:
    user_id = str(payload.get("user_id", ""))
    if user_id and is_demo_user(user_id):
        raise HTTPException(status_code=404, detail="Reports are not enabled for this account")
    # generating spends OpenAI credit — shared link sessions can't trigger it
    block_link_session_writes(request, "make reports")
    resolved = ensure_user_access(request, user_id)
    if not search_report_enabled(resolved):
        raise HTTPException(status_code=404, detail="Reports are not enabled for this account")
    include = [str(x) for x in (payload.get("include") or []) if x][:40]
    exclude = [str(x) for x in (payload.get("exclude") or []) if x][:40]
    return resolved, str(payload.get("query", "")), include, exclude


@router.post("/api/search-report")
def search_report(request: Request, payload: dict = Body(...)):
    """One AI-written report across the reels a search returned (finished
    report in one response; the app uses the streaming route below)."""
    user_id, query, include, exclude = _report_request(request, payload)
    try:
        return build_search_report(user_id, query, include=include, exclude=exclude)
    except ReportError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


@router.post("/api/search-report/stream")
def search_report_stream(request: Request, payload: dict = Body(...)):
    """The same report as server-sent events, so cards render as they are
    written. Access errors are normal HTTP errors (raised before streaming);
    anything after that arrives as an {"event": "error"} frame."""
    user_id, query, include, exclude = _report_request(request, payload)

    def frames():
        try:
            for event in report_events(user_id, query, include=include, exclude=exclude):
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
        except ReportError as exc:
            yield "data: " + json.dumps({"event": "error", "status": exc.status, "detail": str(exc)}) + "\n\n"
        except Exception:
            yield "data: " + json.dumps({"event": "error", "status": 500,
                                         "detail": "Couldn't write the report right now. Try again in a bit."}) + "\n\n"

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/api/recipes")
def recipes(request: Request, user_id: str = Query(default="")):
    """All extracted recipe cards + per-ingredient shopping data + city matrix,
    for the Recipes overlay inside the app."""
    if user_id and is_demo_user(user_id):
        return {"recipes": []}
    resolved = ensure_user_access(request, user_id)
    if not recipes_enabled(resolved):
        raise HTTPException(status_code=404, detail="Recipes is not enabled for this account")
    return build_recipes(resolved, allow_extraction=not is_demo_link_session(request))
