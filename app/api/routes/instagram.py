import hashlib
import hmac
import json
import re
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import settings
from app.services.auth import complete_instagram_link, get_user_by_instagram_user_id
from app.services.jobs import enqueue_reel_job, start_worker_if_needed
from app.services.reel_ingest import append_reel, is_valid_instagram_url


router = APIRouter(prefix="/instagram", tags=["instagram"])

INSTAGRAM_URL_FINDER = re.compile(r"https?://(?:www\.)?instagram\.com/(?:reel|p)/[A-Za-z0-9_-]+/?(?:\?[^\s]+)?", re.IGNORECASE)
LINK_CODE_RE = re.compile(r"\bREEL-\d{6}\b", re.IGNORECASE)


def _verify_signature(raw_body: bytes, signature_header: str) -> bool:
    if not settings.instagram_app_secret:
        return True
    expected = "sha256=" + hmac.new(
        settings.instagram_app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, (signature_header or "").strip())


def _iter_message_events(payload: Any):
    stack = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if isinstance(current.get("sender"), dict) and (
                isinstance(current.get("message"), dict) or isinstance(current.get("postback"), dict)
            ):
                yield current
            for value in current.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)


def _deep_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _deep_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _deep_strings(nested)


def _extract_candidate_urls(message_event: dict) -> list[str]:
    urls = []
    seen = set()
    for text in _deep_strings(message_event):
        for match in INSTAGRAM_URL_FINDER.findall(text):
            normalized = match.strip()
            if normalized not in seen and is_valid_instagram_url(normalized):
                seen.add(normalized)
                urls.append(normalized)
    return urls


def _extract_link_code(message_event: dict) -> str:
    for text in _deep_strings(message_event.get("message", {})):
        match = LINK_CODE_RE.search(text or "")
        if match:
            return match.group(0).upper()
    return ""


def _extract_sender(message_event: dict) -> tuple[str, str]:
    sender = message_event.get("sender") or {}
    sender_id = str(sender.get("id") or "").strip()
    username = str(sender.get("username") or "").strip().lstrip("@")
    return sender_id, username


@router.get("/webhook")
def instagram_webhook_verify(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    if hub_mode == "subscribe" and settings.instagram_webhook_verify_token and hub_verify_token == settings.instagram_webhook_verify_token:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Instagram webhook verification")


@router.post("/webhook")
async def instagram_webhook(request: Request, x_hub_signature_256: str = Header(default="", alias="X-Hub-Signature-256")):
    raw_body = await request.body()
    if not _verify_signature(raw_body, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Instagram signature")

    payload = json.loads(raw_body.decode("utf-8") or "{}")
    linked_accounts = 0
    reels_saved = 0
    ignored_events = 0
    saved_reel_ids: list[str] = []

    for event in _iter_message_events(payload):
        sender_id, sender_username = _extract_sender(event)
        if not sender_id:
            ignored_events += 1
            continue

        link_code = _extract_link_code(event)
        if link_code:
            try:
                complete_instagram_link(link_code, sender_id, instagram_username=sender_username)
                linked_accounts += 1
            except HTTPException:
                ignored_events += 1
            continue

        user = get_user_by_instagram_user_id(sender_id)
        if not user:
            ignored_events += 1
            continue

        for url in _extract_candidate_urls(event):
            reel = append_reel(url, user_id=user["id"], source="instagram")
            job = enqueue_reel_job(reel["id"], user_id=reel["user_id"])
            saved_reel_ids.append(reel["id"])
            reels_saved += 1

    if linked_accounts or reels_saved:
        start_worker_if_needed()

    return JSONResponse(
        {
            "ok": True,
            "linked_accounts": linked_accounts,
            "reels_saved": reels_saved,
            "ignored_events": ignored_events,
            "saved_reel_ids": saved_reel_ids,
        }
    )
