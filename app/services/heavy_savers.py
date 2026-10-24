"""Heavy savers: Instagram people ranked by reels saved today, then in total.

For the admin "Heavy savers" tab. It only lists people and remembers who the
founder crossed off after blocking them by hand in Instagram. Nothing here
blocks, messages or changes anyone's account.

Core users (everyone from before 14 Oct 2026) are never block candidates:
their old Google accounts are left out, and any Instagram account in the keep
list is shown as "core, keep" with no cross-off box.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.services.admin_stats import UTC_OFFSET_MINUTES, _local_day, _norm, _today_local

# Launch day of the Instagram bot. Accounts made before it are core users.
CORE_BEFORE = "2026-10-14"
# Test and own accounts that are not real people.
SKIP_HANDLES = {"url_testing", "url_testing_finale", "clipnest.in", "clipnest"}
# Instagram handles that belong to core users or family. Never block candidates.
KEEP_HANDLES = {"_.scootyyyy"} | {
    h.strip().lower().lstrip("@") for h in os.getenv("HEAVY_SAVERS_KEEP", "").split(",") if h.strip()
}

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS admin_crossed_off (
    user_id TEXT PRIMARY KEY,
    crossed_at TEXT NOT NULL
)
"""


def ensure_table(c: sqlite3.Connection) -> None:
    c.execute(TABLE_SQL)


def set_crossed(c: sqlite3.Connection, user_id: str, crossed: bool) -> None:
    ensure_table(c)
    if crossed:
        c.execute(
            "INSERT OR REPLACE INTO admin_crossed_off (user_id, crossed_at) VALUES (?, ?)",
            (user_id, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
    else:
        c.execute("DELETE FROM admin_crossed_off WHERE user_id = ?", (user_id,))


def heavy_savers(c: sqlite3.Connection, today: str | None = None) -> dict[str, Any]:
    """Everyone from the bot with at least one reel, top savers first.

    Reels counted the same way as the dashboard: our own ad reel left out,
    failed reels left out, days in India time."""
    ensure_table(c)
    today = today or _today_local()
    r_day = _local_day("r.received_at")
    rows = c.execute(
        f"""
        SELECT u.id, u.display_name, u.instagram_username, {_local_day('u.created_at')} AS joined,
               SUM(CASE WHEN {r_day} = ? THEN 1 ELSE 0 END) AS today,
               COUNT(r.id) AS total,
               COUNT(DISTINCT {r_day}) AS days,
               MAX({_norm('r.received_at')}) AS last_reel,
               x.crossed_at
        FROM users u
        JOIN reels r ON r.user_id = u.id
             AND COALESCE(r.source, '') <> 'clipnest_ad' AND r.status <> 'failed'
        LEFT JOIN admin_crossed_off x ON x.user_id = u.id
        WHERE u.id LIKE 'user_ig_%'
        GROUP BY u.id
        """,
        (today,),
    ).fetchall()
    people = []
    for row in rows:
        handle = (row["instagram_username"] or "").strip().lstrip("@")
        if handle.lower() in SKIP_HANDLES:
            continue
        core = handle.lower() in KEEP_HANDLES or str(row["joined"]) < CORE_BEFORE
        name = (row["display_name"] or "").strip()
        people.append({
            "user_id": row["id"],
            "name": "" if name.lower() == handle.lower() else name,
            "handle": handle,
            "url": f"https://www.instagram.com/{handle}/" if handle else "",
            "today": int(row["today"] or 0),
            "total": int(row["total"] or 0),
            "days": int(row["days"] or 0),
            "joined": str(row["joined"]),
            "last_reel": str(row["last_reel"] or ""),
            "core": core,
            "crossed": bool(row["crossed_at"]) and not core,
        })
    people.sort(key=lambda p: (-p["today"], -p["total"], p["handle"].lower()))
    return {
        "today": today,
        "utc_offset_minutes": UTC_OFFSET_MINUTES,
        "people": people,
        "crossed": sum(1 for p in people if p["crossed"]),
        "core": sum(1 for p in people if p["core"]),
    }
