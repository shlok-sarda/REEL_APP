"""Repairs Shlok asked for by hand, run once on the first start that carries
them. Each is claimed with its own maintenance flag before it runs, so with
two processes starting at once only one does it, and a restart never repeats
it. Every step checks the data is still in the shape it was found in and
does nothing otherwise.
"""
from datetime import datetime

from app.db.database import get_connection

# 2026-10-18. Onir signed in with Google outside his library link, got a
# second, empty account, and typed its code into the DM. His reel is on the
# account the bot made for him.
ONIR_JOIN = ("user_ig_a92622ad56e798a9", "user_b41a19e8984d9d25")

# 2026-10-18. Reels that failed in the 17 Oct outage (the shared cache file
# written by two workers at once), each with the person it belongs to. They
# are read again for that same person and nobody else.
OUTAGE_REELS = {
    "reel_1219": "user_ig_aedddbd433e889c9",
    "reel_1220": "user_ig_aedddbd433e889c9",
    "reel_1221": "user_ig_aedddbd433e889c9",
    "reel_1222": "user_ig_aedddbd433e889c9",
    "reel_1223": "user_ig_aedddbd433e889c9",
    "reel_1224": "user_ig_aedddbd433e889c9",
    "reel_1225": "user_ig_1f94fcd4394da14c",
    "reel_1226": "user_c9baa4824d170cfc",
}


def _claim(flag: str) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT OR IGNORE INTO maintenance_flags (flag, executed_at) VALUES (?, ?)",
            (flag, datetime.now().isoformat(timespec="seconds")),
        )
        return cursor.rowcount == 1


def join_onir() -> str:
    if not _claim("join_onir_2026_10_18"):
        return ""
    from app.services.auth import join_accounts

    return join_accounts(*ONIR_JOIN)


def rerun_outage_reels() -> list[str]:
    if not _claim("rerun_outage_reels_2026_10_18"):
        return []
    from app.services.jobs import enqueue_reel_job
    from app.services.reel_ingest import reset_reel_for_retry

    queued = []
    for reel_id, owner in OUTAGE_REELS.items():
        with get_connection() as connection:
            row = connection.execute(
                "SELECT user_id, status FROM reels WHERE id = ?", (reel_id,)
            ).fetchone()
        if not row or row["user_id"] != owner or row["status"] != "failed":
            continue
        reset_reel_for_retry(reel_id)
        enqueue_reel_job(reel_id, user_id=owner)
        queued.append(reel_id)
    return queued


def run_all() -> dict:
    result = {}
    for name, repair in (("join_onir", join_onir), ("rerun_outage_reels", rerun_outage_reels)):
        try:
            result[name] = repair()
        except Exception as exc:  # a repair must never stop the app starting
            result[name] = f"failed: {exc!r}"
    return result
