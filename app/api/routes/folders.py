"""Smart-folders API — create folders from search results, list them, and
accept/reject auto-routed reels. Gated to beta users until rolled out.

Auto-routing itself runs in the processing pipeline (services/folders.route_reel),
not through a user-facing endpoint.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Body, HTTPException, Request

from app.services.auth import ensure_user_access
from app.services import folders as folders_service

router = APIRouter(prefix="/folders", tags=["folders"])


def _beta_users() -> set[str]:
    raw = os.getenv("FOLDERS_BETA_USERS", "user_4a507f088f27007a").strip()
    return {u.strip() for u in raw.split(",") if u.strip()}


def folders_enabled(user_id: str) -> bool:
    users = _beta_users()
    return "all" in users or user_id in users


def _gate(request: Request, user_id: str) -> str:
    resolved = ensure_user_access(request, user_id)
    if not folders_enabled(resolved):
        raise HTTPException(status_code=404, detail="folders not enabled for this account")
    return resolved


@router.get("")
def list_folders(request: Request, user_id: str = ""):
    resolved = _gate(request, user_id)
    return {"user_id": resolved, "folders": folders_service.list_folders(resolved)}


@router.post("/suggest")
def suggest(request: Request, payload: dict = Body(...)):
    resolved = _gate(request, str(payload.get("user_id", "")))
    reel_ids = list(payload.get("reel_ids") or [])
    if not reel_ids:
        raise HTTPException(status_code=400, detail="reel_ids required")
    return folders_service.suggest_meta(resolved, str(payload.get("query", "")), reel_ids)


@router.post("")
def create(request: Request, payload: dict = Body(...)):
    resolved = _gate(request, str(payload.get("user_id", "")))
    name = str(payload.get("name", "")).strip()
    description = str(payload.get("description", "")).strip()
    reel_ids = list(payload.get("reel_ids") or [])
    if not name or not description or not reel_ids:
        raise HTTPException(status_code=400, detail="name, description, reel_ids required")
    return folders_service.create_folder(resolved, name, description,
                                          str(payload.get("query", "")), reel_ids)


@router.get("/{folder_id}")
def detail(request: Request, folder_id: int, user_id: str = ""):
    resolved = _gate(request, user_id)
    data = folders_service.folder_detail(resolved, folder_id)
    if not data:
        raise HTTPException(status_code=404, detail="folder not found")
    return data


@router.post("/{folder_id}/accept")
def accept(request: Request, folder_id: int, payload: dict = Body(...)):
    resolved = _gate(request, str(payload.get("user_id", "")))
    reel_id = str(payload.get("reel_id", ""))
    if not reel_id:
        raise HTTPException(status_code=400, detail="reel_id required")
    return folders_service.set_membership_status(resolved, folder_id, reel_id, "member")


@router.post("/{folder_id}/reject")
def reject(request: Request, folder_id: int, payload: dict = Body(...)):
    resolved = _gate(request, str(payload.get("user_id", "")))
    reel_id = str(payload.get("reel_id", ""))
    if not reel_id:
        raise HTTPException(status_code=400, detail="reel_id required")
    return folders_service.set_membership_status(resolved, folder_id, reel_id, "rejected")


@router.delete("/{folder_id}")
def delete(request: Request, folder_id: int, user_id: str = ""):
    resolved = _gate(request, user_id)
    folders_service.delete_folder(resolved, folder_id)
    return {"ok": True}
