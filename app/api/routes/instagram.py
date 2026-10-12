from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import json
import re
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.db.database import get_connection
from app.services.auth import complete_instagram_link, create_guest_user, get_user_by_instagram_user_id, iso_now, require_admin
from app.services.jobs import enqueue_reel_job, ensure_background_progress
from app.services.instagram_profile import (
    cached_instagram_username,
    fill_username_for_sender,
    resolve_instagram_username,
)
from app.services.instagram_send import send_text
from app.services import nudge
from app.services.reel_ingest import append_reel, canonical_reel_url, get_reel_by_url, is_valid_instagram_url


router = APIRouter(prefix="/instagram", tags=["instagram"])

# Replies go out on their own small pool, not the one that serves pages.
# Meta's send endpoint can hang for its full 25 second timeout; as ordinary
# background tasks, a burst of new senders during one of those spells took
# every page thread and the whole site stopped answering until they expired.
# Here a slow Meta only delays the replies behind it.
_reply_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="dm-reply")


def _reply_later(func, *args) -> None:
    def run():
        try:
            func(*args)
        except Exception as exc:  # a failed reply must never surface anywhere
            print(f"[instagram] reply task failed: {exc}", flush=True)

    _reply_pool.submit(run)


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
            # Keep the table small — retain the most recent 200 rows. Except
            # buffered reels: this table doubles as the holding pen for reels
            # sent before an account existed or past the 20-reel wall, and
            # pruning those would silently lose a reel the person was told
            # was being held. They become prunable once drained. Requests to
            # delete data are kept for the same reason: each one is a promise
            # that is acted on by hand, days later, from the health page.
            connection.execute(
                """
                DELETE FROM instagram_webhook_events
                WHERE outcome NOT IN ('buffered', 'delete_requested')
                  AND id NOT IN (
                    SELECT id FROM instagram_webhook_events ORDER BY id DESC LIMIT 200
                  )
                """
            )
    except Exception as exc:  # pragma: no cover - diagnostics must not crash ingest
        print(f"[instagram] failed to log webhook event: {exc}")


def _log_delete_request(sender_id: str, sender_username: str, user_id: str) -> None:
    """Someone asked for their data to be deleted. Deletion is done by hand
    within 7 days; this row is the to-do list, shown on the health page."""
    _log_webhook_event(
        "delete", sender_id=sender_id, sender_username=sender_username,
        outcome="delete_requested", detail=user_id,
    )


INSTAGRAM_URL_FINDER = re.compile(r"https?://(?:www\.)?instagram\.com/(?:reel|p)/[A-Za-z0-9_-]+/?(?:\?[^\s]+)?", re.IGNORECASE)
LINK_CODE_RE = re.compile(r"\bREEL-\d{6}\b", re.IGNORECASE)
PING_RE = re.compile(r"^\s*ping\s*$", re.IGNORECASE)
# The data deletion page tells people to send these words.
DELETE_RE = re.compile(r"\bdelete\s+(?:all\s+)?(?:my\s+(?:clipnest\s+)?(?:data|account)|everything)\b", re.IGNORECASE)

# What a tapped button, chip or ice breaker means. The payload is ours, set
# where the button was made. Anything not listed here still gets an answer
# (their library), because a tap that is met with silence reads as broken.
# DELETE_YES and DELETE_NO are deliberately absent: deletion is done by hand,
# so no message of ours carries those chips.
TAP_TRIGGERS = {
    "ICE_HOW": "ask_how",
    "ICE_WHAT": "ask_what",
    "ICE_FREE": "ask_free",
    "ICE_LIBRARY": "plain_message",
    "MENU_LIBRARY": "plain_message",
    "MENU_DELETE": "delete_request",
}
# Ice breakers typed into Instagram's own dashboard may arrive with no payload
# of ours, or as an ordinary message, so the question itself is matched too.
ICE_BREAKER_QUESTIONS = {
    "how do i save a reel here": "ask_how",
    "how do i save a reel": "ask_how",
    "how to share a reel": "ask_how",
    "what does clipnest do": "ask_what",
    "what does it do": "ask_what",
    "is it free": "ask_free",
    "where is my library": "plain_message",
}
_QUESTION_STARTS = {"how", "what", "why", "where", "can", "does", "do", "is"}
_FREE_WORDS = re.compile(r"\b(?:free|cost|costs|price|paid|pay|charge|charges|money)\b")
_LIBRARY_WORDS = re.compile(r"\b(?:library|link|my reels|my saved)\b")
_SAVE_WORDS = re.compile(r"\b(?:save|saved|saving|send|share|sharing|add|reel|reels)\b")


def _plain_words(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split())


def _tap(message_event: dict) -> tuple[bool, str, str]:
    """(was it a tap, payload, title) for a button, ice breaker, menu item or
    quick reply chip. A typed message is (False, "", "")."""
    postback = message_event.get("postback")
    if isinstance(postback, dict):
        return True, str(postback.get("payload") or "").strip(), str(postback.get("title") or "").strip()
    message = message_event.get("message")
    quick_reply = message.get("quick_reply") if isinstance(message, dict) else None
    if isinstance(quick_reply, dict):
        return True, str(quick_reply.get("payload") or "").strip(), str(message.get("text") or "").strip()
    return False, "", ""


def _trigger_for_tap(payload: str, title: str) -> str:
    trigger = TAP_TRIGGERS.get((payload or "").strip().upper())
    if trigger:
        return trigger
    return ICE_BREAKER_QUESTIONS.get(_plain_words(title), "plain_message")


def _typed_text(message_event: dict) -> str:
    message = message_event.get("message")
    text = message.get("text") if isinstance(message, dict) else ""
    return text if isinstance(text, str) else ""


def _trigger_for_text(text: str) -> str:
    """What a typed message with no reel in it is asking for.

    Keyword matching only: no model is called, so this costs nothing and can
    only ever choose between replies that are already written.
    """
    if DELETE_RE.search(text or ""):
        return "delete_request"
    words = _plain_words(text)
    if words in ICE_BREAKER_QUESTIONS:
        return ICE_BREAKER_QUESTIONS[words]
    first = words.split(" ", 1)[0] if words else ""
    if not ((text or "").strip().endswith("?") or first in _QUESTION_STARTS):
        return "plain_message"
    if _FREE_WORDS.search(words):
        return "typed_free"
    if _LIBRARY_WORDS.search(words):
        return "plain_message"
    if _SAVE_WORDS.search(words):
        return "typed_how"
    return "typed_what"


def _only_a_reaction(message_event: dict) -> bool:
    """A heart on one of our messages, or a read receipt. Not a message."""
    if isinstance(message_event.get("message"), dict) or isinstance(message_event.get("postback"), dict):
        return False
    return isinstance(message_event.get("reaction"), dict) or isinstance(message_event.get("read"), dict)


def _saved_title(reel_id: str) -> str:
    try:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT item_name FROM reel_items WHERE reel_id = ? AND item_name != '' ORDER BY id ASC LIMIT 1",
                (reel_id,),
            ).fetchone()
        return row["item_name"] if row else ""
    except Exception:
        return ""


def _verify_signature(raw_body: bytes, signature_header: str) -> bool:
    if not settings.instagram_app_secret:
        # Local dev has no secret and must keep working. Production without
        # one would trust any POST, which with the launch switches on means
        # free account creation plus paid processing for anyone: fail closed.
        return not settings.is_production
    expected = "sha256=" + hmac.new(
        settings.instagram_app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    # As bytes: compare_digest raises on non-ASCII text, and a forged header
    # should get a 401, not a server error.
    return hmac.compare_digest(expected.encode("utf-8"), (signature_header or "").strip().encode("utf-8", "replace"))


def _iter_message_events(payload: Any):
    stack = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if isinstance(current.get("sender"), dict) and (
                isinstance(current.get("message"), dict)
                or isinstance(current.get("postback"), dict)
                or isinstance(current.get("reaction"), dict)
                or isinstance(current.get("read"), dict)
            ):
                # Skip echoes. When the app account sends a DM, Instagram
                # delivers a copy back with the business account as `sender`,
                # which previously logged as a stranger "not linked to any
                # account" and made ordinary replies look like failed signups.
                message = current.get("message")
                if not (isinstance(message, dict) and message.get("is_echo")):
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


def _send_ping_reply(sender_id: str, sender_username: str) -> None:
    result = send_text(sender_id, "pong. ClipNest can reach you here.")
    _log_webhook_event(
        "ping", sender_id=sender_id, sender_username=sender_username,
        outcome="sent" if result["ok"] else "send_failed", detail=result["detail"],
    )


def _describe_message(message_event: dict) -> str:
    """Shape of a message we could not read a reel out of.

    Keys and attachment types plus the hostnames of any URLs, never the text
    itself. A native reel share does not necessarily carry an
    instagram.com/reel/ permalink, and without seeing the actual structure
    the fix is guesswork.
    """
    import re as _re

    message = message_event.get("message") or {}
    parts = [f"msg_keys={sorted(message.keys())}"]
    attachments = message.get("attachments")
    if isinstance(attachments, list):
        kinds = []
        for att in attachments:
            if isinstance(att, dict):
                payload = att.get("payload") if isinstance(att.get("payload"), dict) else {}
                kinds.append(f"{att.get('type')}({sorted(payload.keys())})")
        parts.append(f"attachments={kinds}")
    hosts = set()
    for text in _deep_strings(message):
        for match in _re.findall(r"https?://([A-Za-z0-9.-]+)", text or ""):
            hosts.add(match)
    if hosts:
        parts.append(f"url_hosts={sorted(hosts)}")
    return " ".join(parts)[:400]


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


def _has_attachment(message_event: dict) -> bool:
    """True when the message carries a share or media, not just typed text."""
    attachments = (message_event.get("message") or {}).get("attachments")
    return isinstance(attachments, list) and bool(attachments)


def _extract_link_code(message_event: dict) -> str:
    for text in _deep_strings(message_event.get("message", {})):
        match = LINK_CODE_RE.search(text or "")
        if match:
            return match.group(0).upper()
    return ""


def _is_ping(message_event: dict) -> bool:
    """True when the message is the bare word PING, the outbound-DM probe."""
    for text in _deep_strings(message_event.get("message", {})):
        if PING_RE.match(text or ""):
            return True
    return False


def _extract_sender(message_event: dict) -> tuple[str, str]:
    """Sender id plus handle. Instagram sends only the id.

    `sender.username` is read first because it costs nothing, but Instagram
    does not populate it on messaging webhooks — so in practice the handle
    always comes from the cached Graph lookup below. Without that, every
    stored sender_username is an empty string and no row in the admin list
    can be matched to a real person.
    """
    sender = message_event.get("sender") or {}
    sender_id = str(sender.get("id") or "").strip()
    username = str(sender.get("username") or "").strip().lstrip("@")
    if sender_id and not username:
        try:
            if _handle_needed_now():
                username = resolve_instagram_username(sender_id)
            else:
                # The lookup is a network call that can hang for 8 seconds.
                # When nothing is decided by the handle, answer Instagram
                # first and fill the name in afterwards.
                username, known = cached_instagram_username(sender_id)
                if not known:
                    _reply_later(fill_username_for_sender, sender_id)
        except Exception:
            username = ""
    return sender_id, username


def _handle_needed_now() -> bool:
    """The handle decides something only while the test allowlist is what
    lets a sender in or gets them a reply. With both launch switches on,
    everyone is let in and it is only a display name."""
    if not settings.guest_test_senders:
        return False
    return not (settings.guest_autocreate_for_everyone and settings.dm_reply_for_everyone)


def _over_cap(user_id: str, url: str) -> bool:
    """Would saving this use a reel the account no longer has this month?
    A reel already in the library is not a new one, so it is let through."""
    return nudge.over_monthly_cap(user_id) and not get_reel_by_url(canonical_reel_url(url), user_id=user_id)


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
            if _over_cap(user_id, url):
                _log_webhook_event(
                    "reel", sender_id=sender_id, sender_username=sender_username,
                    outcome="over_month_cap", detail=url,
                )
                continue
            reel = append_reel(url, user_id=user_id, source="instagram")
            if reel.get("status") != "completed":
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
async def instagram_webhook(
    request: Request,
    background: BackgroundTasks,
    x_hub_signature_256: str = Header(default="", alias="X-Hub-Signature-256"),
):
    # Only reading the body happens on the event loop. Handling a delivery
    # looks up each new sender over the network (up to 8s) and waits on the
    # database, and on the single loop that froze every page for everyone.
    raw_body = await request.body()
    return await run_in_threadpool(_handle_delivery, raw_body, x_hub_signature_256, background)


def _handle_delivery(raw_body: bytes, x_hub_signature_256: str, background: BackgroundTasks) -> JSONResponse:
    if not _verify_signature(raw_body, x_hub_signature_256):
        _log_webhook_event("delivery", outcome="rejected", detail="signature verification failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Instagram signature")

    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except (ValueError, RecursionError):
        # Signed but unreadable. Nothing can be done with it and asking for it
        # again would only fail again, so acknowledge and move on.
        _log_webhook_event("delivery", outcome="rejected", detail="body is not valid JSON")
        return JSONResponse({"ok": True, "ignored": "unreadable body"})
    crashed_events = 0
    linked_accounts = 0
    reels_saved = 0
    ignored_events = 0
    saved_reel_ids: list[str] = []
    # Instagram delivers each shared reel as its own message event, so a bulk
    # save arrives as many events in one payload. Collect who saved what and
    # reply once each after the loop: once per reel would fire five DMs for
    # five reels, and replying mid-loop would quote a count that is still
    # climbing.
    pending_replies: dict[str, dict] = {}

    events = list(_iter_message_events(payload))
    # Always record that a delivery arrived, so an empty event list is
    # distinguishable from "Instagram never called us at all".
    _log_webhook_event(
        "delivery",
        outcome=f"{len(events)} message event(s)",
        detail="top-level keys: " + ",".join(sorted(payload.keys())) if isinstance(payload, dict) else "non-dict payload",
    )

    for event in events:
        try:
            sender_id, sender_username = _extract_sender(event)
            if not sender_id:
                ignored_events += 1
                _log_webhook_event("event", outcome="ignored", detail="no sender id in event")
                continue

            if _only_a_reaction(event):
                # Never answered, and not counted as them writing to us: a
                # heart on a bot message must not earn "Here is your library".
                ignored_events += 1
                _log_webhook_event(
                    "event", sender_id=sender_id, sender_username=sender_username,
                    outcome="ignored_reaction",
                )
                continue

            if settings.outbound_dm_test and _is_ping(event):
                _reply_later(_send_ping_reply, sender_id, sender_username)
                continue

            # The 24h window and the last-call timer both hang off this.
            nudge.record_inbound(sender_id)

            tapped, tap_payload, tap_title = _tap(event)
            if tapped:
                # Counted per payload: the only direct measure of whether
                # anyone taps what the bot sends.
                _log_webhook_event(
                    "tap", sender_id=sender_id, sender_username=sender_username,
                    outcome=f"tap:{tap_payload or 'none'}"[:80], detail=tap_title[:200],
                )

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
            if not user and (
                settings.guest_autocreate_for_everyone
                or nudge.sender_allowed(sender_id, sender_username)
            ):
                user = create_guest_user(sender_id, sender_username)
                # The stamp above ran before this row existed, so the reply window
                # would stay shut and the first reel would get no acknowledgement.
                nudge.record_inbound(sender_id)
                _log_webhook_event(
                    "guest", sender_id=sender_id, sender_username=sender_username,
                    outcome="created" if user else "create_failed",
                    detail=(user or {}).get("id", ""),
                )
                # Anything they sent before the account existed is sitting in the
                # buffer. Replay it now, or a reel shared while the allowlist was
                # still wrong is silently lost. append_reel dedupes on
                # (user_id, url), so replaying twice cannot duplicate anything.
                if user and user.get("id"):
                    drained = _drain_buffered_reels(sender_id, sender_username, user["id"])
                    if drained:
                        reels_saved += drained
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

            if tapped:
                # A tap is a direct question and always gets its answer. It
                # must never fall through to the reel branches below, where
                # it would be read as a message with no reel in it.
                trigger = _trigger_for_tap(tap_payload, tap_title)
                if trigger == "delete_request":
                    _log_delete_request(sender_id, sender_username, user["id"])
                _reply_later(nudge.fire, user["id"], trigger, "", True)
                continue

            # The wall. Hold the reel rather than process it, and rather than
            # reject it: signing in then saves everything waiting in one go.
            if nudge.is_locked(user["id"]):
                held = _extract_candidate_urls(event)
                for url in held:
                    _log_webhook_event(
                        "reel", sender_id=sender_id, sender_username=sender_username,
                        outcome="buffered", detail=url,
                    )
                if held:
                    _reply_later(nudge.fire, user["id"], "reel_held")
                    ignored_events += 1
                    continue

            urls = _extract_candidate_urls(event)
            if not urls:
                _log_webhook_event(
                    "reel", sender_id=sender_id, sender_username=sender_username,
                    outcome="ignored",
                    detail="no reel url found :: " + _describe_message(event),
                )
                # Recovery path: any message re-sends their link. The IGSID is
                # permanent, so deleting the conversation must not cost someone
                # their library. A share we could not read a reel out of (story
                # mention, photo, a video with no permalink) is different: "here
                # is your library" tells them it saved, so say that it did not.
                trigger = "unreadable_share" if _has_attachment(event) else _trigger_for_text(_typed_text(event))
                if trigger == "delete_request":
                    # Recorded and answered whatever else is in this delivery.
                    _log_delete_request(sender_id, sender_username, user["id"])
                    _reply_later(nudge.fire, user["id"], trigger)
                elif sender_id not in pending_replies:
                    _reply_later(nudge.fire, user["id"], trigger)
            saved_here = 0
            already_saved = 0
            held_here = 0
            capped_here = 0
            already_title = ""
            for url in urls:
                # Checked per reel, not only per message: one message can
                # carry many links, and checking once let a single text with
                # sixty links walk a guest straight through the wall.
                if nudge.is_locked(user["id"]):
                    _log_webhook_event(
                        "reel", sender_id=sender_id, sender_username=sender_username,
                        outcome="buffered", detail=url,
                    )
                    held_here += 1
                    continue
                if _over_cap(user["id"], url):
                    # Not buffered: a held reel is saved later, and this one
                    # must not be read or paid for at all.
                    _log_webhook_event(
                        "reel", sender_id=sender_id, sender_username=sender_username,
                        outcome="over_month_cap", detail=url,
                    )
                    capped_here += 1
                    continue
                reel = append_reel(url, user_id=user["id"], source="instagram")
                if reel.get("status") == "completed":
                    # They sent a reel that is already in their library. Queueing
                    # it again would pay for a second full extraction of the same
                    # video and change nothing they can see.
                    already_saved += 1
                    already_title = _saved_title(reel["id"])
                    _log_webhook_event(
                        "reel", sender_id=sender_id, sender_username=sender_username,
                        outcome="already_saved", detail=url,
                    )
                    continue
                job = enqueue_reel_job(reel["id"], user_id=reel["user_id"])
                saved_reel_ids.append(reel["id"])
                reels_saved += 1
                saved_here += 1
                _log_webhook_event(
                    "reel", sender_id=sender_id, sender_username=sender_username,
                    outcome="saved", detail=url,
                )
            if saved_here:
                # Tracked so the recovery reply does not also fire for someone who
                # just saved something.
                pending_replies[sender_id] = {"user_id": user["id"], "saved": saved_here}
                # Only the first-ever reel gets an immediate word. Five minutes of
                # silence on a stranger's first message reads as broken, not as
                # processing. Every later reel waits for its title.
                _reply_later(nudge.fire, user["id"], "reel_saved")
            if held_here:
                _reply_later(nudge.fire, user["id"], "reel_held")
            elif capped_here:
                _reply_later(nudge.fire, user["id"], "month_cap")
            elif already_saved and not saved_here and sender_id not in pending_replies:
                # Nothing new to process. Say so, with the name it was saved
                # under, rather than a library link that tells them nothing.
                _reply_later(nudge.fire, user["id"], "already_saved", already_title)
        except Exception as exc:
            # One message that cannot be handled must not cost the others in
            # the same delivery. It is recorded, and the delivery is answered
            # with an error at the end so Instagram sends it again: saving a
            # reel twice is harmless, losing one is not.
            crashed_events += 1
            print(f"[instagram] event handling failed: {exc!r}", flush=True)
            _log_webhook_event("event", outcome="crashed", detail=repr(exc))

    # Replies are decided in app/services/nudge, not here. This route's job
    # is to record what happened and say so; what the bot says about it is one
    # decision in one place.

    if linked_accounts or reels_saved:
        # After the 200 goes out: this recovers orphans, rewrites the CSV and
        # may spawn the worker, none of which Meta should wait on.
        background.add_task(ensure_background_progress)

    return JSONResponse(
        status_code=500 if crashed_events else 200,
        content={
            "ok": not crashed_events,
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
    require_admin(request)
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
