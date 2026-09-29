"""Tell someone their reel is ready, with a link to their library.

Sent when processing finishes rather than when the reel is saved. The
library deliberately hides reels that have no title yet (see
load_recent_reels), so a link sent at save time is guaranteed to open an
empty page for the several minutes the pipeline takes. Waiting costs a
little silence and buys a link that actually shows something.

Only ever a reply to a message they sent, so it stays inside Meta's 24 hour
window - unless the queue is badly backed up, in which case the send fails
and is logged rather than retried, because there is no way to reopen that
window from this side.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import settings
from app.db.database import get_connection
from app.services.instagram_send import send_text


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat((value or "").strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _log(kind: str, sender_id: str, username: str, outcome: str, detail: str) -> None:
    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO instagram_webhook_events
                    (received_at, kind, sender_id, sender_username, link_code, outcome, detail)
                VALUES (?, ?, ?, '', '', ?, ?)
                """,
                (_now().isoformat(timespec="seconds"), kind, sender_id, outcome, detail[:500]),
            )
    except Exception:
        pass


def _replies_allowed(user_row) -> bool:
    if settings.dm_reply_for_everyone:
        return True
    user_id = (user_row["id"] or "").strip().lower()
    if user_id in settings.dm_reply_accounts:
        return True
    handle = (user_row["instagram_username"] or "").strip().lower().lstrip("@")
    igsid = (user_row["instagram_user_id"] or "").strip().lower()
    if handle in settings.guest_test_senders or igsid in settings.guest_test_senders:
        return True
    # No admin bypass: an admin account is not an opted-in account, and
    # treating it as one sent a DM to a handle nobody had listed.
    email = (user_row["email"] or "").strip().lower()
    return bool(email) and email in settings.dm_reply_accounts


def notify_reel_ready(user_id: str, reel_id: str) -> None:
    """DM the owner that a reel finished, at most once per cooldown."""
    try:
        with get_connection() as connection:
            user = connection.execute(
                "SELECT id, email, instagram_user_id, instagram_username, library_token, last_dm_at "
                "FROM users WHERE id = ? LIMIT 1",
                (user_id,),
            ).fetchone()
            if not user:
                return
            igsid = (user["instagram_user_id"] or "").strip()
            if not igsid or not _replies_allowed(user):
                return

            last = _parse(user["last_dm_at"] or "")
            if last and _now() - last < timedelta(minutes=settings.dm_cooldown_minutes):
                _log("notify", igsid, "", "skipped_cooldown", f"{user_id} last dm {user['last_dm_at']}")
                return

            title_row = connection.execute(
                "SELECT item_name FROM reel_items WHERE reel_id = ? AND item_name != '' LIMIT 1",
                (reel_id,),
            ).fetchone()
            total = connection.execute(
                "SELECT COUNT(*) AS n FROM reels WHERE user_id = ?", (user_id,)
            ).fetchone()["n"]

        token = (user["library_token"] or "").strip()
        if not token:
            from app.services.auth import get_or_create_library_token

            token = get_or_create_library_token(user_id)
        base = (settings.public_base_url or "").rstrip("/")
        if not base.startswith("http") or not token:
            _log("notify", igsid, "", "skipped", "no absolute library link available")
            return
        link = f"{base}/g/{token}"

        title = (title_row["item_name"] if title_row else "") or ""
        if title:
            text = f"Ready: {title}. Your library: {link}"
        elif total > 1:
            text = f"Ready. That is {total} reels now. Your library: {link}"
        else:
            text = f"Ready. Your library is here: {link}"

        result = send_text(igsid, text)
        if result["ok"]:
            with get_connection() as connection:
                connection.execute(
                    "UPDATE users SET last_dm_at = ? WHERE id = ?",
                    (_now().isoformat(timespec="seconds"), user_id),
                )
        _log(
            "notify", igsid, "",
            "sent" if result["ok"] else "send_failed",
            f"reel={reel_id} title={title!r} :: {result['detail']}",
        )
    except Exception as exc:
        _log("notify", "", "", "notify_crashed", str(exc))
