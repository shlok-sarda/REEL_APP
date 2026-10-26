"""What people wrote to the bot, word for word, for the admin Messages tab.

The webhook keeps every typed message and tapped question as a "said" row
(kept 30 days). This groups them by person, newest conversation first, so
hand replies can be written without opening each chat in Instagram. Nothing
here sends, reads Instagram, or marks a chat as seen.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any

from app.services.admin_stats import UTC_OFFSET_MINUTES, _norm


def _local_time(ts: str) -> str:
    raw = (ts or "").replace("T", " ")[:19]
    try:
        moment = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw
    return (moment + timedelta(minutes=UTC_OFFSET_MINUTES)).strftime("%d %b, %I:%M %p").lstrip("0")


def recent_messages(c: sqlite3.Connection, days: int = 7) -> dict[str, Any]:
    rows = c.execute(
        f"""
        SELECT received_at, sender_id, sender_username, detail
        FROM instagram_webhook_events
        WHERE kind = 'said' AND {_norm('received_at')} >= datetime('now', ?)
        ORDER BY id
        """,
        (f"-{int(days)} days",),
    ).fetchall()
    handles: dict[str, str] = {}
    try:
        for r in c.execute("SELECT igsid, username FROM instagram_profile_cache WHERE username <> ''"):
            handles[str(r[0])] = str(r[1])
    except sqlite3.Error:
        pass
    people: dict[str, dict[str, Any]] = {}
    for at, sender, username, words in rows:
        sender = str(sender or "")
        p = people.setdefault(sender, {"sender_id": sender, "handle": "", "last": "", "messages": []})
        p["handle"] = str(username or "") or p["handle"] or handles.get(sender, "")
        p["last"] = str(at)
        p["messages"].append({"at": _local_time(str(at)), "words": str(words or "")})
    ordered = sorted(people.values(), key=lambda p: p["last"], reverse=True)
    for p in ordered:
        p["url"] = f"https://www.instagram.com/{p['handle']}/" if p["handle"] else ""
    return {"people": ordered, "count": len(rows), "days": days}
