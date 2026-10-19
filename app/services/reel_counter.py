"""Reels people sent the bot versus reels that ended up saved.

One reel_receipts row per reel shared, written by the Instagram webhook the
moment a delivery arrives, keyed by Meta's message id so a delivery Meta
sends again counts once. The webhook writes what it decided (queued for
saving, already in their library, held, refused and why); whether a queued
reel was then saved or failed is read from the reel and its job when the
dashboard asks, so the processing pipeline is not touched at all.

Writing a row must never slow down or break a save: every write here
swallows its own errors.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from app.db.database import get_connection

# What the webhook decided for one reel.
QUEUED = "queued"        # handed to the worker; saved or failed is read later
DUPLICATE = "duplicate"  # already in that person's library
HELD = "held"            # kept until they sign in or their account exists
REFUSED = "refused"      # never processed; `reason` says why
AD = "ad"                # our own reel shared back, counted on its own

# Short reason codes and the words the dashboard shows for them.
REASONS = {
    "no_link_reel": "Reel with no link",
    "no_link_post": "Post with no link",
    "private": "Private or deleted",
    "download_failed": "Could not download",
    "our_error": "Broke on our side",
    "monthly_cap": "Monthly cap",
    "held": "Held until sign in",
}


def message_id(event: dict, sender_id: str) -> str:
    """Meta's id for the message. Every message carries one (`mid`); the
    fallback keeps a retried delivery of an odd event on the same key."""
    for holder in (event.get("message"), event.get("postback")):
        if isinstance(holder, dict) and holder.get("mid"):
            return str(holder["mid"])
    return f"{sender_id}:{event.get('timestamp') or ''}"


def record(
    event: dict,
    sender_id: str,
    user_id: str,
    item: str,
    outcome: str,
    reason: str = "",
    reel_id: str = "",
    received_at: str = "",
) -> None:
    """Count one shared reel, once per message and item. Never raises."""
    try:
        from app.services.auth import iso_now

        with get_connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO reel_receipts
                    (message_id, item, sender_id, user_id, received_at, outcome, reason, reel_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id(event, sender_id), (item or "")[:300], sender_id, user_id or "",
                    received_at or iso_now(), outcome, reason, reel_id or "",
                ),
            )
    except Exception as exc:  # counting must never cost a reel
        print(f"[reel_counter] record skipped: {exc}", flush=True)


def resolve_held(sender_id: str, item: str, user_id: str, outcome: str, reason: str = "", reel_id: str = "") -> None:
    """A held reel was let through when they signed in or their account was
    made: move its oldest held row on to what happened. Never raises."""
    try:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE reel_receipts SET outcome = ?, reason = ?, reel_id = ?, user_id = ?
                WHERE id = (SELECT id FROM reel_receipts WHERE sender_id = ? AND item = ? AND outcome = ?
                            ORDER BY id LIMIT 1)
                """,
                (outcome, reason, reel_id or "", user_id, sender_id, (item or "")[:300], HELD),
            )
    except Exception as exc:
        print(f"[reel_counter] resolve_held skipped: {exc}", flush=True)


def _blank() -> dict[str, Any]:
    return {"received": 0, "duplicates": 0, "processed": 0, "in_progress": 0, "not_processed": 0,
            "gap": 0, "ad": 0, "reasons": {k: 0 for k in REASONS}}


def counts(c: sqlite3.Connection, day_sql: str, today: str, week_start: str, people_sql: str) -> dict[str, Any]:
    """Today, last 7 days and all time. `day_sql` turns a column into the
    dashboard's local day; `people_sql` is a condition on user_id that keeps
    only real people (a reel sent before the account existed has no user yet
    and counts too)."""
    out = {"today": _blank(), "last_7": _blank(), "all": _blank(), "since": ""}
    try:
        rows = c.execute(
            f"""
            SELECT {day_sql.format(col='rr.received_at')} AS day, rr.outcome, rr.reason,
                   r.status AS reel_status,
                   (SELECT j.status || '|' || j.error_message FROM processing_jobs j
                    WHERE j.reel_id = rr.reel_id AND j.job_type = 'process_reel'
                    ORDER BY j.id DESC LIMIT 1) AS job
            FROM reel_receipts rr
            LEFT JOIN reels r ON r.id = rr.reel_id
            WHERE rr.user_id = '' OR rr.user_id IN (SELECT id FROM users WHERE {people_sql})
            """
        ).fetchall()
        since = c.execute("SELECT MIN(received_at) FROM reel_receipts").fetchone()[0]
    except sqlite3.Error as exc:
        print(f"[reel_counter] counts skipped: {exc}", flush=True)
        return out
    out["since"] = (since or "")[:10]
    for row in rows:
        state, reason = _state(row)
        windows = [out["all"]]
        if row["day"] >= week_start:
            windows.append(out["last_7"])
        if row["day"] == today:
            windows.append(out["today"])
        for w in windows:
            if state == AD:
                w["ad"] += 1
                continue
            w["received"] += 1
            if state == DUPLICATE:
                w["duplicates"] += 1
            elif state == "processed":
                w["processed"] += 1
            elif state == "in_progress":
                w["in_progress"] += 1
            else:
                w["not_processed"] += 1
                w["reasons"][reason] = w["reasons"].get(reason, 0) + 1
    for w in (out["today"], out["last_7"], out["all"]):
        w["gap"] = w["received"] - w["duplicates"] - w["processed"]
    return out


def _state(row: sqlite3.Row) -> tuple[str, str]:
    """(processed | in_progress | duplicate | ad | not_processed, reason)."""
    outcome = row["outcome"]
    if outcome in (AD, DUPLICATE):
        return outcome, ""
    if outcome == HELD:
        return "not_processed", "held"
    if outcome != QUEUED:
        return "not_processed", row["reason"] or "our_error"
    status = row["reel_status"]
    if status == "completed":
        return "processed", ""
    if status is None:
        # The reel row is gone: they deleted it from their library, so it
        # was saved first.
        return "processed", ""
    job_status, _, error = (row["job"] or "").partition("|")
    if "Reel unavailable" in error and (status == "failed" or job_status == "failed"):
        return "not_processed", "private"
    if job_status == "failed":
        return "not_processed", "our_error"
    if status == "failed":
        return "not_processed", "download_failed"
    return "in_progress", ""
