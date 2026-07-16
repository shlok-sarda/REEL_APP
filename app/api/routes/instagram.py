import hashlib
import hmac
import json
import re
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import settings
from app.db.database import get_connection
from app.services.auth import complete_instagram_link, current_user, get_user_by_instagram_user_id, iso_now
from app.services.jobs import enqueue_reel_job, ensure_background_progress
from app.services.reel_ingest import append_reel, is_valid_instagram_url


router = APIRouter(prefix="/instagram", tags=["instagram"])


def _log_webhook_event(
    kind: str,
    *,
    sender_id: str = "",
    sender_username: str = "",
    link_code: str = "",
    outcome: str = "",
    detail: str = "",
) -> None:
    """Persist a webhook diagnostic row. Never let logging break the webhook."""
    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO instagram_webhook_events
                    (received_at, kind, sender_id, sender_username, link_code, outcome, detail)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (iso_now(), kind, sender_id, sender_username, link_code, outcome, detail[:500]),
            )
            # Keep the table small — retain the most recent 200 rows.
            connection.execute(
                """
                DELETE FROM instagram_webhook_events
                WHERE id NOT IN (
                    SELECT id FROM instagram_webhook_events ORDER BY id DESC LIMIT 200
                )
                """
            )
    except Exception as exc:  # pragma: no cover - diagnostics must not crash ingest
        print(f"[instagram] failed to log webhook event: {exc}")

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


def _drain_buffered_reels(sender_id: str, sender_username: str, user_id: str) -> int:
    """Ingest reels the sender shared before their link completed.

    New users DM the link code and immediately start sharing reels; a reel
    that outruns link completion arrives from a sender the webhook doesn't
    recognize and used to be dropped silently. Those events are kept as
    outcome='buffered' with the URL in detail — replay them the moment the
    link lands. append_reel dedupes on (user_id, url), so replaying twice
    can't duplicate a reel.
    """
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT detail FROM instagram_webhook_events
            WHERE kind = 'reel' AND outcome = 'buffered' AND sender_id = ?
            ORDER BY id ASC
            """,
            (sender_id,),
        ).fetchall()
    saved = 0
    for row in rows:
        url = (row["detail"] or "").strip()
        if not is_valid_instagram_url(url):
            continue
        try:
            reel = append_reel(url, user_id=user_id, source="instagram")
            enqueue_reel_job(reel["id"], user_id=reel["user_id"])
            saved += 1
            _log_webhook_event(
                "reel", sender_id=sender_id, sender_username=sender_username,
                outcome="saved", detail=f"drained after link: {url}",
            )
        except Exception as exc:
            _log_webhook_event(
                "reel", sender_id=sender_id, sender_username=sender_username,
                outcome="drain_failed", detail=f"{url} :: {exc}",
            )
    if saved:
        try:
            with get_connection() as connection:
                connection.execute(
                    "UPDATE instagram_webhook_events SET outcome = 'drained' WHERE kind = 'reel' AND outcome = 'buffered' AND sender_id = ?",
                    (sender_id,),
                )
        except Exception:
            pass
    return saved


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
        _log_webhook_event("delivery", outcome="rejected", detail="signature verification failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Instagram signature")

    payload = json.loads(raw_body.decode("utf-8") or "{}")
    linked_accounts = 0
    reels_saved = 0
    ignored_events = 0
    saved_reel_ids: list[str] = []

    events = list(_iter_message_events(payload))
    # Always record that a delivery arrived, so an empty event list is
    # distinguishable from "Instagram never called us at all".
    _log_webhook_event(
        "delivery",
        outcome=f"{len(events)} message event(s)",
        detail="top-level keys: " + ",".join(sorted(payload.keys())) if isinstance(payload, dict) else "non-dict payload",
    )

    for event in events:
        sender_id, sender_username = _extract_sender(event)
        if not sender_id:
            ignored_events += 1
            _log_webhook_event("event", outcome="ignored", detail="no sender id in event")
            continue

        link_code = _extract_link_code(event)
        if link_code:
            try:
                linked_user = complete_instagram_link(link_code, sender_id, instagram_username=sender_username)
                linked_accounts += 1
                _log_webhook_event(
                    "link", sender_id=sender_id, sender_username=sender_username,
                    link_code=link_code, outcome="linked",
                )
                if linked_user.get("id"):
                    reels_saved += _drain_buffered_reels(sender_id, sender_username, linked_user["id"])
            except HTTPException as exc:
                ignored_events += 1
                _log_webhook_event(
                    "link", sender_id=sender_id, sender_username=sender_username,
                    link_code=link_code, outcome="link_failed", detail=str(exc.detail),
                )
            continue

        user = get_user_by_instagram_user_id(sender_id)
        if not user:
            # Buffer instead of drop: keep each URL so it can be replayed when
            # this sender's link code arrives (possibly later in this same
            # webhook delivery — event order within a payload is arbitrary).
            buffered_urls = _extract_candidate_urls(event)
            for url in buffered_urls:
                _log_webhook_event(
                    "reel", sender_id=sender_id, sender_username=sender_username,
                    outcome="buffered", detail=url,
                )
            if not buffered_urls:
                _log_webhook_event(
                    "reel", sender_id=sender_id, sender_username=sender_username,
                    outcome="ignored", detail="sender id not linked to any account",
                )
            ignored_events += 1
            continue

        urls = _extract_candidate_urls(event)
        if not urls:
            _log_webhook_event(
                "reel", sender_id=sender_id, sender_username=sender_username,
                outcome="ignored", detail="no instagram reel url found in message",
            )
        for url in urls:
            reel = append_reel(url, user_id=user["id"], source="instagram")
            job = enqueue_reel_job(reel["id"], user_id=reel["user_id"])
            saved_reel_ids.append(reel["id"])
            reels_saved += 1
            _log_webhook_event(
                "reel", sender_id=sender_id, sender_username=sender_username,
                outcome="saved", detail=url,
            )

    if linked_accounts or reels_saved:
        ensure_background_progress()

    return JSONResponse(
        {
            "ok": True,
            "linked_accounts": linked_accounts,
            "reels_saved": reels_saved,
            "ignored_events": ignored_events,
            "saved_reel_ids": saved_reel_ids,
        }
    )


@router.get("/debug/events")
def instagram_debug_events(request: Request, limit: int = Query(default=40, ge=1, le=200)):
    """Recent Instagram webhook activity, for diagnosing linking/ingest.

    Requires a signed-in user. Returns the raw event log (most recent first)
    plus the current config gates so we can tell whether Instagram is even
    reaching the server.
    """
    if not current_user(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in first")
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT received_at, kind, sender_id, sender_username, link_code, outcome, detail
            FROM instagram_webhook_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return JSONResponse(
        {
            "config": {
                "app_username_set": bool(settings.instagram_app_username),
                "verify_token_set": bool(settings.instagram_webhook_verify_token),
                "app_secret_set": bool(settings.instagram_app_secret),
            },
            "event_count": len(rows),
            "events": [dict(row) for row in rows],
        }
    )
