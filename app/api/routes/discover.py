"""Discover routes: the reel map and recipes pages + their data endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.services.auth import current_user, ensure_user_access
from app.services.discover import build_map_pins, build_recipes
from app.services.library import is_demo_user
from app.ui_ux.discover_pages import build_map_html, build_recipes_html

router = APIRouter(tags=["discover"])


def _page_user(request: Request, user_id: str) -> str | None:
    """Resolve who the page is for: the logged-in user, or the demo account
    (so the pages can be previewed without a session, matching /app/{demo})."""
    if user_id and is_demo_user(user_id):
        return user_id
    user = current_user(request)
    return user["id"] if user else None


@router.get("/map", response_class=HTMLResponse)
def map_page(request: Request, user_id: str = Query(default="")):
    resolved = _page_user(request, user_id)
    if not resolved:
        return RedirectResponse(url="/", status_code=303)
    return HTMLResponse(build_map_html(resolved))


@router.get("/recipes", response_class=HTMLResponse)
def recipes_page(request: Request, user_id: str = Query(default="")):
    resolved = _page_user(request, user_id)
    if not resolved:
        return RedirectResponse(url="/", status_code=303)
    return HTMLResponse(build_recipes_html(resolved))


@router.get("/api/map-data")
def map_data(request: Request, user_id: str = Query(default="")):
    if user_id and is_demo_user(user_id):
        return {"pins": [], "pending_places": 0}
    resolved = ensure_user_access(request, user_id)
    return build_map_pins(resolved)


@router.get("/api/recipes-data")
def recipes_data(request: Request, user_id: str = Query(default="")):
    if user_id and is_demo_user(user_id):
        return {"recipes": []}
    resolved = ensure_user_access(request, user_id)
    return build_recipes(resolved)
