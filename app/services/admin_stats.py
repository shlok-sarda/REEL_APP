"""Numbers for the admin dashboard, and the small daily bot history behind it.

Everything here is read-only against the main tables except two tiny tables,
bot_daily and bot_daily_senders, which keep one row per day per metric. They
exist because instagram_webhook_events is trimmed to its last 200 rows, so
"how many people wrote to the bot on Tuesday" would otherwise be lost within
days. Every other number is computed live from tables that keep full history
(users, reels, nudge_log).

Day boundaries are in the founder's time (UTC+5:30 by default), not the
server's UTC, so "today" on the page means today for the person reading it.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.db.database import get_connection

# Minutes east of UTC that a "day" is measured in. 330 = India.
UTC_OFFSET_MINUTES = int(os.getenv("DASHBOARD_UTC_OFFSET_MINUTES", "330").strip() or 330)
# Measured all-in cost of reading one reel, in rupees (see memory: Rs 0.82 lab).
REEL_COST_RUPEES = float(os.getenv("DASHBOARD_REEL_COST_RUPEES", "0.82").strip() or 0.82)
# How long one computed snapshot is reused, so a few quick reloads on a phone
# do not run the whole query set each time. Short enough to still feel live.
CACHE_SECONDS = 20

SEED_FLAG = "bot_daily_seeded_v1"

BUCKETS = ["0", "1", "2 to 4", "5 to 9", "10 to 19", "20 to 49", "50+"]

# Only accounts made by the bot count as people. The older accounts are the
# founder's own and testers, so the dashboard starts at the real users.
PEOPLE = "id LIKE 'user_ig_%'"
REELS = "user_id IN (SELECT id FROM users WHERE id LIKE 'user_ig_%')"
# Our own reel (the ad) saved into someone's library is not a reel they saved.
THEIRS = "COALESCE(source, '') <> 'clipnest_ad'"

# Webhook outcomes worth a daily counter. Anything else is noise for this page.
COUNTED_OUTCOMES = {"needs_human", "ad_referral", "created", "over_month_cap", "saved"}
# Outbound rows: the bot talking, not a person.
OUTBOUND_KINDS = {"nudge", "delivery"}

_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"at": 0.0, "data": None}
_seeded = False


# --------------------------------------------------------------------------
# SQL helpers
# --------------------------------------------------------------------------

def _norm(col: str) -> str:
    """Timestamps are stored three ways (naive local, ISO with T, ISO with
    +00:00). All of them are UTC in practice; cut to 'YYYY-MM-DD HH:MM:SS'."""
    return f"substr(replace({col}, 'T', ' '), 1, 19)"


def _local_day(col: str) -> str:
    return f"date({_norm(col)}, '+{UTC_OFFSET_MINUTES} minutes')"


def _today_local() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=UTC_OFFSET_MINUTES)).strftime("%Y-%m-%d")


def _days_back(n: int) -> list[str]:
    today = datetime.now(timezone.utc) + timedelta(minutes=UTC_OFFSET_MINUTES)
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n - 1, -1, -1)]


def _local_day_of(ts: str) -> str:
    """Python twin of _local_day for one ISO timestamp."""
    raw = (ts or "").replace("T", " ")[:19]
    try:
        moment = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        moment = datetime.utcnow()
    return (moment + timedelta(minutes=UTC_OFFSET_MINUTES)).strftime("%Y-%m-%d")


def _series(rows: list, days: list[str]) -> list[int]:
    by_day = {str(r[0]): int(r[1] or 0) for r in rows}
    return [by_day.get(d, 0) for d in days]


def _has_column(connection: sqlite3.Connection, table: str, column: str) -> bool:
    try:
        return any(r[1] == column for r in connection.execute(f"PRAGMA table_info({table})"))
    except sqlite3.Error:
        return False


# --------------------------------------------------------------------------
# Daily bot history: written on every webhook event, seeded once from the log
# --------------------------------------------------------------------------

def record_bot_event(
    connection: sqlite3.Connection,
    kind: str,
    sender_id: str,
    outcome: str,
    received_at: str,
) -> None:
    """One or two tiny upserts per webhook row. Never raises."""
    try:
        day = _local_day_of(received_at)
        if sender_id and kind not in OUTBOUND_KINDS:
            connection.execute(
                "INSERT OR IGNORE INTO bot_daily_senders (day, sender_id) VALUES (?, ?)",
                (day, sender_id),
            )
        if outcome in COUNTED_OUTCOMES:
            connection.execute(
                """
                INSERT INTO bot_daily (day, metric, value) VALUES (?, ?, 1)
                ON CONFLICT(day, metric) DO UPDATE SET value = value + 1
                """,
                (day, outcome),
            )
    except sqlite3.Error as exc:  # pragma: no cover - stats must never break ingest
        print(f"[admin_stats] record_bot_event skipped: {exc}")


def seed_bot_daily(connection: sqlite3.Connection) -> bool:
    """Fill bot_daily from whatever the trimmed webhook log still holds, once.
    Returns True when the seed ran this call."""
    global _seeded
    if _seeded:
        return False
    try:
        row = connection.execute(
            "SELECT executed_at FROM maintenance_flags WHERE flag = ? LIMIT 1", (SEED_FLAG,)
        ).fetchone()
        if row:
            _seeded = True
            return False
        events = connection.execute(
            "SELECT kind, sender_id, outcome, received_at FROM instagram_webhook_events ORDER BY id"
        ).fetchall()
        for e in events:
            record_bot_event(connection, e["kind"], e["sender_id"], e["outcome"], e["received_at"])
        connection.execute(
            "INSERT OR REPLACE INTO maintenance_flags (flag, executed_at) VALUES (?, ?)",
            (SEED_FLAG, datetime.utcnow().isoformat(timespec="seconds")),
        )
        _seeded = True
        return True
    except sqlite3.Error as exc:
        print(f"[admin_stats] seed skipped: {exc}")
        return False


# --------------------------------------------------------------------------
# Who stays: join-day cohorts
# --------------------------------------------------------------------------

def cohorts(active_days: dict[str, set[str]], today: str, max_rows: int = 30) -> dict[str, Any]:
    """Join-day cohorts from each person's set of local days with a reel.

    Joined = the day of their first reel. Day 1 = sent a reel on any day after
    the join day. Day 3 = sent one on the third day after joining or later.
    A row shows a day's number once that day has started (marked so far while
    it is still running); the overall numbers only take a cohort once that day
    is over, so yesterday's people do not drag day 1 down this morning."""
    today_d = datetime.strptime(today, "%Y-%m-%d").date()
    by_join: dict[str, list[set[str]]] = {}
    for days in active_days.values():
        if days:
            by_join.setdefault(min(days), []).append(days)
    rows = []
    totals = {"d1_people": 0, "d1_stayed": 0, "d3_people": 0, "d3_stayed": 0}
    for join in sorted(by_join, reverse=True):
        group = by_join[join]
        join_d = datetime.strptime(join, "%Y-%m-%d").date()
        age = (today_d - join_d).days
        d1_cut = (join_d + timedelta(days=1)).strftime("%Y-%m-%d")
        d3_cut = (join_d + timedelta(days=3)).strftime("%Y-%m-%d")
        d1 = sum(1 for days in group if max(days) >= d1_cut) if age >= 1 else None
        d3 = sum(1 for days in group if max(days) >= d3_cut) if age >= 3 else None
        if d1 is not None and age > 1:
            totals["d1_people"] += len(group)
            totals["d1_stayed"] += d1
        if d3 is not None and age > 3:
            totals["d3_people"] += len(group)
            totals["d3_stayed"] += d3
        rows.append({"day": join, "joined": len(group), "day1": d1, "day3": d3,
                     "day1_so_far": age == 1, "day3_so_far": age == 3})
    return {"rows": rows[:max_rows], **totals}


# --------------------------------------------------------------------------
# The numbers
# --------------------------------------------------------------------------

def dashboard_data(force: bool = False) -> dict[str, Any]:
    """Every number the three pages show, computed in one pass. Cached for
    CACHE_SECONDS so a burst of reloads costs one query set."""
    now = time.time()
    with _cache_lock:
        if not force and _cache["data"] is not None and now - _cache["at"] < CACHE_SECONDS:
            return _cache["data"]
    started = time.perf_counter()
    with get_connection() as connection:
        seed_bot_daily(connection)
        data = _compute(connection)
    data["computed_in_ms"] = round((time.perf_counter() - started) * 1000, 1)
    data["computed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _cache_lock:
        _cache["at"] = now
        _cache["data"] = data
    return data


def _compute(c: sqlite3.Connection) -> dict[str, Any]:
    today = _today_local()
    days30 = _days_back(30)
    days7 = days30[-7:]
    first30 = days30[0]
    month_start = today[:8] + "01"
    u_day = _local_day("created_at")
    r_day = _local_day("received_at")
    now_local = f"datetime('now', '+{UTC_OFFSET_MINUTES} minutes')"

    # ---- people ---------------------------------------------------------
    p = c.execute(
        f"""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN COALESCE(google_sub, '') = '' THEN 1 ELSE 0 END) AS guests,
               SUM(CASE WHEN COALESCE(google_sub, '') <> '' THEN 1 ELSE 0 END) AS signed_in,
               SUM(CASE WHEN id LIKE 'user_ig_%' THEN 1 ELSE 0 END) AS from_instagram,
               SUM(CASE WHEN id LIKE 'user_ig_%' AND COALESCE(google_sub, '') <> '' THEN 1 ELSE 0 END) AS guests_who_signed_in,
               SUM(CASE WHEN {u_day} = ? THEN 1 ELSE 0 END) AS today,
               SUM(CASE WHEN {u_day} >= ? THEN 1 ELSE 0 END) AS last_7,
               SUM(CASE WHEN {u_day} >= ? THEN 1 ELSE 0 END) AS last_30,
               SUM(CASE WHEN {u_day} >= ? THEN 1 ELSE 0 END) AS this_month
        FROM users WHERE {PEOPLE}
        """,
        (today, days7[0], first30, month_start),
    ).fetchone()
    people_per_day = _series(
        c.execute(
            f"SELECT {u_day} AS d, COUNT(*) FROM users WHERE {PEOPLE} AND {u_day} >= ? GROUP BY d", (first30,)
        ).fetchall(),
        days30,
    )
    ig_per_day = _series(
        c.execute(
            f"SELECT {u_day} AS d, COUNT(*) FROM users WHERE id LIKE 'user_ig_%' AND {u_day} >= ? GROUP BY d", (first30,)
        ).fetchall(),
        days30,
    )
    # Came back a week later: saved a reel, or opened the app, 7+ days after joining.
    returned = c.execute(
        f"""
        SELECT COUNT(*) AS eligible,
               SUM(CASE WHEN
                    EXISTS (SELECT 1 FROM reels r WHERE r.user_id = u.id AND COALESCE(r.source, '') <> 'clipnest_ad'
                            AND {_norm('r.received_at')} >= datetime({_norm('u.created_at')}, '+7 days'))
                 OR (COALESCE(u.last_login_at, '') <> ''
                     AND {_norm('u.last_login_at')} >= datetime({_norm('u.created_at')}, '+7 days'))
               THEN 1 ELSE 0 END) AS returned
        FROM users u
        WHERE u.{PEOPLE} AND {_norm('u.created_at')} <= datetime('now', '-7 days')
        """
    ).fetchone()

    # ---- reels ----------------------------------------------------------
    r = c.execute(
        f"""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
               SUM(CASE WHEN status NOT IN ('completed', 'failed') THEN 1 ELSE 0 END) AS in_progress,
               SUM(CASE WHEN {r_day} = ? THEN 1 ELSE 0 END) AS today,
               SUM(CASE WHEN {r_day} >= ? THEN 1 ELSE 0 END) AS last_7,
               SUM(CASE WHEN {r_day} >= ? THEN 1 ELSE 0 END) AS last_30,
               SUM(CASE WHEN {r_day} >= ? THEN 1 ELSE 0 END) AS this_month,
               COUNT(DISTINCT CASE WHEN {r_day} = ? THEN user_id END) AS savers_today,
               COUNT(DISTINCT CASE WHEN {r_day} >= ? THEN user_id END) AS savers_7
        FROM reels WHERE {REELS} AND {THEIRS}
        """,
        (today, days7[0], first30, month_start, today, days7[0]),
    ).fetchone()
    reels_per_day = _series(
        c.execute(
            f"SELECT {r_day} AS d, COUNT(*) FROM reels WHERE {REELS} AND {THEIRS} AND {r_day} >= ? GROUP BY d", (first30,)
        ).fetchall(),
        days30,
    )
    failed_per_day = _series(
        c.execute(
            f"SELECT {r_day} AS d, COUNT(*) FROM reels WHERE {REELS} AND {THEIRS} AND status = 'failed' AND {r_day} >= ? GROUP BY d",
            (first30,),
        ).fetchall(),
        days30,
    )

    # ---- reels per person, in buckets -----------------------------------
    bucket_rows = c.execute(
        f"""
        SELECT CASE
                 WHEN n = 0 THEN '0'
                 WHEN n = 1 THEN '1'
                 WHEN n < 5 THEN '2 to 4'
                 WHEN n < 10 THEN '5 to 9'
                 WHEN n < 20 THEN '10 to 19'
                 WHEN n < 50 THEN '20 to 49'
                 ELSE '50+' END AS bucket,
               COUNT(*) AS people
        FROM (SELECT u.id, (SELECT COUNT(*) FROM reels r WHERE r.user_id = u.id AND COALESCE(r.source, '') <> 'clipnest_ad') AS n FROM users u WHERE u.{PEOPLE})
        GROUP BY bucket
        """
    ).fetchall()
    ad_items = int(
        c.execute(f"SELECT COUNT(*) FROM reels WHERE {REELS} AND NOT ({THEIRS})").fetchone()[0] or 0
    )
    # People with no reel saved who sent a post we could not save.
    zero_post_only = int(
        c.execute(
            f"""
            SELECT COUNT(DISTINCT n.user_id) FROM nudge_log n JOIN users u ON u.id = n.user_id
            WHERE u.{PEOPLE} AND n.message_key = 'm15_photo_post'
              AND NOT EXISTS (SELECT 1 FROM reels r WHERE r.user_id = u.id AND COALESCE(r.source, '') <> 'clipnest_ad')
            """
        ).fetchone()[0] or 0
    )
    bucket_map = {row["bucket"]: int(row["people"] or 0) for row in bucket_rows}
    buckets = [{"label": b, "people": bucket_map.get(b, 0)} for b in BUCKETS]

    # ---- who stays --------------------------------------------------------
    active: dict[str, set[str]] = {}
    for row in c.execute(
        f"SELECT DISTINCT user_id, {r_day} AS d FROM reels WHERE {REELS} AND {THEIRS}"
    ).fetchall():
        active.setdefault(row["user_id"], set()).add(str(row["d"]))
    stays = cohorts(active, today)

    # ---- monthly cap ----------------------------------------------------
    cap = int(settings.monthly_reel_cap or 0)
    cap_live_row = c.execute(
        "SELECT executed_at FROM maintenance_flags WHERE flag = 'monthly_reel_cap_live' LIMIT 1"
    ).fetchone()
    cap_since = max(month_start + " 00:00:00", (cap_live_row["executed_at"] if cap_live_row else "").replace("T", " ")[:19])
    at_cap = 0
    near_cap = 0
    if cap > 0:
        has_override = _has_column(c, "users", "monthly_cap_override")
        own_cap = "CASE WHEN COALESCE(u.monthly_cap_override, 0) > 0 THEN u.monthly_cap_override ELSE ? END" if has_override else "?"
        rows = c.execute(
            f"""
            SELECT (SELECT COUNT(*) FROM reels r WHERE r.user_id = u.id AND COALESCE(r.source, '') <> 'clipnest_ad' AND {_norm('r.received_at')} >= ?) AS n,
                   {own_cap} AS cap
            FROM users u WHERE u.{PEOPLE}
            """,
            (cap_since, cap),
        ).fetchall()
        for row in rows:
            n, user_cap = int(row["n"] or 0), int(row["cap"] or 0)
            if user_cap and n >= user_cap:
                at_cap += 1
            elif user_cap and n >= user_cap * 0.8:
                near_cap += 1

    # ---- easter egg groups ----------------------------------------------
    egg: dict[str, Any] = {"live": False, "groups": []}
    if _has_column(c, "users", "own_reel_group"):
        egg["live"] = True
        for row in c.execute(
            """
            SELECT own_reel_group AS grp, COUNT(*) AS people,
                   SUM(CASE WHEN EXISTS (SELECT 1 FROM reels r WHERE r.user_id = users.id AND COALESCE(r.source, '') <> 'clipnest_ad') THEN 1 ELSE 0 END) AS saved_a_reel
            FROM users WHERE own_reel_group <> '' GROUP BY own_reel_group
            """
        ).fetchall():
            egg["groups"].append(
                {"group": row["grp"], "people": int(row["people"] or 0), "saved_a_reel": int(row["saved_a_reel"] or 0)}
            )

    # ---- bot -------------------------------------------------------------
    wrote_rows = c.execute(
        "SELECT day, COUNT(*) FROM bot_daily_senders WHERE day >= ? GROUP BY day", (first30,)
    ).fetchall()
    wrote_per_day = _series(wrote_rows, days30)
    wrote_total = int(c.execute("SELECT COUNT(DISTINCT sender_id) FROM bot_daily_senders").fetchone()[0] or 0)
    metric_series: dict[str, list[int]] = {}
    metric_totals: dict[str, int] = {}
    for metric in sorted(COUNTED_OUTCOMES):
        metric_series[metric] = _series(
            c.execute(
                "SELECT day, value FROM bot_daily WHERE metric = ? AND day >= ?", (metric, first30)
            ).fetchall(),
            days30,
        )
        metric_totals[metric] = int(
            c.execute("SELECT COALESCE(SUM(value), 0) FROM bot_daily WHERE metric = ?", (metric,)).fetchone()[0] or 0
        )
    history_from = c.execute("SELECT MIN(day) FROM bot_daily_senders").fetchone()[0] or ""

    n_day = _local_day("sent_at")
    ad_keys = {
        "m24_ad_hello": "Hello from the ad",
        "m29_own_reel_egg": "Easter egg answer",
        "m25_ad_how": "How does it work",
        "m26_ad_free": "Is it really free",
        "m27_ad_share": "I want to share a reel",
    }
    ad_counts = {k: {"label": v, "total": 0, "last_7": 0, "today": 0} for k, v in ad_keys.items()}
    for row in c.execute(
        f"""
        SELECT message_key AS k, COUNT(*) AS total,
               SUM(CASE WHEN {n_day} >= ? THEN 1 ELSE 0 END) AS last_7,
               SUM(CASE WHEN {n_day} = ? THEN 1 ELSE 0 END) AS today
        FROM nudge_log WHERE message_key IN ({','.join('?' * len(ad_keys))}) GROUP BY k
        """,
        (days7[0], today, *ad_keys.keys()),
    ).fetchall():
        ad_counts[row["k"]].update(total=int(row["total"] or 0), last_7=int(row["last_7"] or 0), today=int(row["today"] or 0))
    ad_hello_per_day = _series(
        c.execute(
            f"SELECT {n_day} AS d, COUNT(*) FROM nudge_log WHERE message_key IN ('m24_ad_hello', 'm29_own_reel_egg') AND {n_day} >= ? GROUP BY d",
            (first30,),
        ).fetchall(),
        days30,
    )
    # First reel acknowledged (m1) and first library sent (m2): the funnel
    # from "wrote" to "has a library", with full history.
    funnel = {}
    for key, label in (("m1_first_ack", "First reel saved"), ("m2_first_library", "Got their library link"), ("m3_quiet_nudge", "Nudged after going quiet"), ("m4_home_screen", "Asked to add to home screen")):
        row = c.execute(
            f"SELECT COUNT(DISTINCT user_id) AS people, SUM(CASE WHEN {n_day} >= ? THEN 1 ELSE 0 END) AS last_7 FROM nudge_log WHERE message_key = ?",
            (days7[0], key),
        ).fetchone()
        funnel[key] = {"label": label, "people": int(row["people"] or 0), "last_7": int(row["last_7"] or 0)}
    waiting = c.execute(
        f"SELECT COUNT(*) FROM instagram_webhook_events WHERE outcome = 'needs_human' AND {_norm('received_at')} >= datetime('now', '-7 days')"
    ).fetchone()[0]

    # ---- older accounts, reported once and left out of everything above ----
    older = c.execute(
        f"""
        SELECT COUNT(*) AS people,
               (SELECT COUNT(*) FROM reels WHERE NOT ({REELS}) AND {THEIRS}) AS reels
        FROM users WHERE NOT ({PEOPLE})
        """
    ).fetchone()

    # ---- reels sent versus saved (counted at the webhook) ------------------
    from app.services import reel_counter

    sent = reel_counter.counts(
        c, _local_day("{col}"), today, days7[0], PEOPLE
    )

    # ---- cost -------------------------------------------------------------
    def rupees(n: int) -> float:
        return round(n * REEL_COST_RUPEES, 2)

    return {
        "today": today,
        "days30": days30,
        "utc_offset_minutes": UTC_OFFSET_MINUTES,
        "people": {
            **{k: int(p[k] or 0) for k in p.keys()},
            "per_day": people_per_day,
            "ig_per_day": ig_per_day,
            "returned_after_week": int(returned["returned"] or 0),
            "eligible_for_return": int(returned["eligible"] or 0),
        },
        "reels": {
            **{k: int(r[k] or 0) for k in r.keys()},
            "per_day": reels_per_day,
            "failed_per_day": failed_per_day,
        },
        "buckets": buckets,
        "stays": stays,
        "ad_items": ad_items,
        "zero_post_only": zero_post_only,
        "older": {"people": int(older["people"] or 0), "reels": int(older["reels"] or 0)},
        "cap": {"cap": cap, "at_cap": at_cap, "near_cap": near_cap, "since": cap_since, "refused": metric_totals.get("over_month_cap", 0)},
        "cost": {
            "per_reel": REEL_COST_RUPEES,
            "today": rupees(int(r["today"] or 0)),
            "this_month": rupees(int(r["this_month"] or 0)),
            "total": rupees(int(r["total"] or 0)),
        },
        "egg": egg,
        "sent": sent,
        "bot": {
            "wrote_per_day": wrote_per_day,
            "wrote_today": wrote_per_day[-1],
            "wrote_7": sum(wrote_per_day[-7:]),
            "wrote_total_people": wrote_total,
            "series": metric_series,
            "totals": metric_totals,
            "history_from": history_from,
            "ad": ad_counts,
            "ad_hello_per_day": ad_hello_per_day,
            "funnel": funnel,
            "waiting_for_human_7d": int(waiting or 0),
        },
    }
