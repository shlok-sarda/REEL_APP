"""Discover data APIs: reel-map pins and per-reel recipe cards.

No standalone pages here — the map is a full-screen overlay INSIDE the main
app (users install the web app to their home screen, so everything must stay
on one URL), and recipes are per-reel actions in the reel sheet.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query, Request

from app.services.auth import block_demo_link_writes, ensure_user_access, is_demo_link_session
from app.services.discover import (
    build_map_pins,
    build_recipes,
    extract_reel_recipe,
    recipes_enabled,
    reel_recipe_status,
)
from app.services.library import is_demo_user

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
    block_demo_link_writes(request, "extract recipes")
    resolved = ensure_user_access(request, user_id)
    return extract_reel_recipe(resolved, reel_id)


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
