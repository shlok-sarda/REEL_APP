"""Every message the @clipnest.in account sends, and who sent it: the bot or
Shlok by hand from the Instagram app (2026-10-26).

Instagram sends a copy ("echo") of every message the account sends, whoever
typed it. The bot notes the id Meta gives each of its own sends, so an echo
whose id the bot never sent is a hand reply. Whether a person's message got
an answer is read from this table by the daily unanswered messages report.
Which side wrote a row is decided when it is read, so it does not matter
whether the echo or the bot's own note lands first. Kept 30 days.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.db.database import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _thirty_days_ago() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(timespec="seconds")


def _save(mid: str, recipient_id: str, by_bot: bool, words: str) -> None:
    mid = (mid or "").strip()
    if not mid:
        return
    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO dm_outgoing (mid, recipient_id, sent_at, by_bot, echoed, words)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(mid) DO UPDATE SET
                    by_bot = MAX(by_bot, excluded.by_bot),
                    echoed = MAX(echoed, excluded.echoed),
                    recipient_id = CASE WHEN recipient_id = '' THEN excluded.recipient_id ELSE recipient_id END,
                    words = CASE WHEN words = '' THEN excluded.words ELSE words END
                """,
                (mid, recipient_id or "", _now(), 1 if by_bot else 0, 0 if by_bot else 1, (words or "")[:500]),
            )
            connection.execute("DELETE FROM dm_outgoing WHERE sent_at < ?", (_thirty_days_ago(),))
    except Exception as exc:  # pragma: no cover - a log row must never cost a reply
        print(f"[dm_outgoing] failed to note a sent message: {exc}")


def note_bot_send(recipient_id: str, body: dict, response_text: str) -> None:
    """The bot sent this. Meta's reply carries the message id."""
    try:
        mid = str(json.loads(response_text or "{}").get("message_id") or "")
    except (ValueError, AttributeError):
        return
    message = body.get("message") if isinstance(body, dict) else None
    words = str(message.get("text") or "[card or buttons]") if isinstance(message, dict) else ""
    _save(mid, recipient_id, True, words)


def note_echo(event: dict) -> None:
    """Instagram's copy of something the account sent."""
    message = event.get("message") if isinstance(event, dict) else None
    if not isinstance(message, dict):
        return
    recipient_id = str((event.get("recipient") or {}).get("id") or "")
    words = str(message.get("text") or "").strip()
    if not words:
        kinds = {str(a.get("type") or "") for a in (message.get("attachments") or []) if isinstance(a, dict)}
        words = "[" + (", ".join(sorted(k for k in kinds if k)) or "attachment") + "]"
    _save(str(message.get("mid") or ""), recipient_id, False, words)
