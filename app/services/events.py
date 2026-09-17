"""Landing-page funnel counters.

Exists for one reason: a paid traffic test has to be readable afterwards. The
last organic run produced 26 link clicks and 0 signups, which cannot say
whether people bounced on arrival, looked at the demo and left unconvinced, or
never found anything to click. These three counters separate those cases.

Deliberately minimal. No IP, no user agent, no referrer, no third-party
script — just an allowlisted event name and a random per-browser id so repeat
visits can be told apart from distinct people.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.database import get_connection

# Allowlisted so a public endpoint cannot be used to write arbitrary rows.
LANDING_EVENTS = frozenset({"landing_view", "demo_click", "signup"})

_MAX_VISITOR = 64
_MAX_SOURCE = 40


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_landing_event(event: str, visitor: str = "", source: str = "") -> bool:
    """Write one funnel row. Returns False for anything not allowlisted.

    Never raises: a failed counter must not take down a page view or, worse,
    a signup. Analytics is the least important thing happening in the request.
    """
    if event not in LANDING_EVENTS:
        return False
    # Strip anything that is not plain identifier text — these strings are
    # attacker-controlled on a public endpoint and get read back in reports.
    clean_visitor = "".join(c for c in (visitor or "") if c.isalnum() or c in "-_")[:_MAX_VISITOR]
    clean_source = "".join(c for c in (source or "") if c.isalnum() or c in "-_")[:_MAX_SOURCE]
    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO landing_events (created_at, event, visitor, source)
                VALUES (?, ?, ?, ?)
                """,
                (_iso_now(), event, clean_visitor, clean_source),
            )
    except Exception:
        return False
    return True


def funnel_summary(days: int = 30) -> dict:
    """Counts and conversion rates for the last `days` days.

    `people` counts distinct browsers, which is the number that matters when
    judging an ad test; `hits` is kept alongside it so an inflated total from
    one person refreshing is visible rather than silently averaged in.
    """
    since = f"-{max(1, int(days))} days"
    rows: list = []
    try:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT event,
                       COUNT(*) AS hits,
                       COUNT(DISTINCT NULLIF(visitor, '')) AS people
                  FROM landing_events
                 WHERE created_at >= datetime('now', ?)
                 GROUP BY event
                """,
                (since,),
            ).fetchall()
    except Exception:
        rows = []

    by_event = {r["event"]: {"hits": r["hits"], "people": r["people"]} for r in rows}
    views = by_event.get("landing_view", {}).get("people", 0)
    demos = by_event.get("demo_click", {}).get("people", 0)
    signups = by_event.get("signup", {}).get("people", 0)

    def pct(part: int, whole: int) -> float:
        return round(100.0 * part / whole, 1) if whole else 0.0

    return {
        "days": days,
        "events": by_event,
        "funnel": {
            "landing_view": views,
            "demo_click": demos,
            "signup": signups,
        },
        "rates": {
            "view_to_demo": pct(demos, views),
            "view_to_signup": pct(signups, views),
            "demo_to_signup": pct(signups, demos),
        },
    }
