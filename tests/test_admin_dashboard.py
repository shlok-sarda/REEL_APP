"""Checks for the admin dashboard. Plain python, no pytest needed:

    python3 tests/test_admin_dashboard.py

Runs the app against a throwaway database with sample people and reels, then
checks: a logged-out visitor and a signed-in non-admin get 404, the admin
gets all three pages and the JSON, the reels-per-person buckets are exactly
right, and the daily bot counters survive the webhook log trim.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

work = Path(tempfile.mkdtemp(prefix="dash_test_"))
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{work / 'app.db'}",
        "STORAGE_DIR": str(work / "st"),
        "MEDIA_DIR": str(work / "md"),
        "QUEUE_JANITOR": "off",
        "APP_ENV": "development",
        "PUBLIC_BASE_URL": "http://127.0.0.1:8017",
        "ADMIN_EMAILS": "admin@test.local",
        "OPENAI_API_KEY": "sk-disabled-local-test",
        "APIFY_TOKEN": "",
        "MONTHLY_REEL_CAP": "50",
    }
)

from starlette.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db.database import get_connection  # noqa: E402
from app.db.init_db import initialize_database  # noqa: E402

initialize_database()

NOW = datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


# People and reels: the bucket layout is 0, 1, 2 to 4, 5 to 9, 10 to 19, 20 to 49, 50+.
PEOPLE = [
    ("admin", "admin@test.local", 3, 60),   # id, email, reels, days ago joined
    ("plain", "plain@test.local", 0, 40),
    ("user_ig_1", "", 1, 0),                 # guest, joined today
    ("user_ig_2", "", 4, 2),
    ("user_ig_3", "", 7, 10),
    ("user_ig_4", "", 12, 12),
    ("user_ig_5", "", 25, 20),
    ("user_ig_6", "", 50, 30),
    ("user_ig_7", "", 0, 1),
]
# Only bot accounts (user_ig_*) count; admin and plain are "older accounts".
EXPECTED_BUCKETS = {"0": 1, "1": 1, "2 to 4": 1, "5 to 9": 1, "10 to 19": 1, "20 to 49": 1, "50+": 1}

def seed() -> None:
    with get_connection() as c:
        # Startup makes a "default" account; drop it so the sample set is exact,
        # and pin the cap's go-live date into the past so sample reels count.
        c.execute("DELETE FROM users WHERE id = 'default'")
        c.execute("INSERT OR REPLACE INTO maintenance_flags (flag, executed_at) VALUES ('monthly_reel_cap_live', ?)", (iso(NOW - timedelta(days=365)),))
        for uid, email, reels, days_ago in PEOPLE:
            joined = NOW - timedelta(days=days_ago, hours=1)
            c.execute(
                "INSERT INTO users (id, display_name, email, google_sub, created_at, last_login_at) VALUES (?, ?, ?, ?, ?, ?)",
                (uid, uid, email, (uid + "_sub") if email else None, iso(joined), iso(NOW) if uid == "admin" else ""),
            )
            for i in range(reels):
                # Reels land over the last day, so the monthly cap (counted from
                # the 1st) sees the 50-reel person at the cap.
                when = max(joined, NOW - timedelta(days=1)) + timedelta(minutes=5 * i)
                status = "failed" if (uid == "user_ig_5" and i < 2) else "completed"
                c.execute(
                    "INSERT INTO reels (id, user_id, url, shortcode, received_at, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"{uid}_r{i}", uid, f"https://www.instagram.com/reel/{uid}{i}/", f"{uid}{i}", iso(when), status, iso(when), iso(when)),
                )
        # Webhook rows that will be trimmed, plus a few recent ones.
        for i in range(230):
            c.execute(
                "INSERT INTO instagram_webhook_events (received_at, kind, sender_id, outcome, detail) VALUES (?, ?, ?, ?, ?)",
                (iso(NOW - timedelta(days=5, minutes=i)), "reel", f"sender{i % 7}", "saved", "old"),
            )
        c.execute(
            "INSERT INTO instagram_webhook_events (received_at, kind, sender_id, outcome, detail) VALUES (?, ?, ?, ?, ?)",
            (iso(NOW), "human", "sender_today", "needs_human", "hi"),
        )
        c.execute(
            "INSERT INTO reels (id, user_id, url, shortcode, received_at, status, source, created_at, updated_at) VALUES ('ad_r', 'user_ig_7', 'https://www.instagram.com/reel/ADx/', 'ADx', ?, 'completed', 'clipnest_ad', ?, ?)",
            (iso(NOW), iso(NOW), iso(NOW)),
        )
        c.execute("UPDATE users SET instagram_username = 'cap_tester' WHERE id = 'user_ig_6'")
        c.execute("INSERT INTO nudge_log (user_id, message_key, sent_at) VALUES ('user_ig_1', 'm24_ad_hello', ?)", (iso(NOW),))
        c.execute("INSERT INTO nudge_log (user_id, message_key, sent_at) VALUES ('user_ig_1', 'm26_ad_free', ?)", (iso(NOW),))



failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


with TestClient(app, client=("127.0.0.1", 50000)) as client:
    seed()
    # 1. Logged out: every dashboard address is "not found".
    for path in ("/admin/dashboard", "/admin/dashboard/people", "/admin/dashboard/bot", "/admin/dashboard/features", "/admin/dashboard.json"):
        res = client.get(path)
        check(f"logged out gets 404 at {path}", res.status_code == 404, str(res.status_code))

    # 2. A signed-in non-admin: still "not found".
    res = client.get("/dev-login", params={"user_id": "plain"}, follow_redirects=False)
    check("dev-login works for a plain user", res.status_code == 303, str(res.status_code))
    for path in ("/admin/dashboard", "/admin/dashboard/people", "/admin/dashboard/bot", "/admin/dashboard/features", "/admin/dashboard.json"):
        res = client.get(path)
        check(f"non-admin gets 404 at {path}", res.status_code == 404, str(res.status_code))
    check("non-admin session says not admin", client.get("/auth/session").json().get("user", {}).get("is_admin") is False)

    # 3. The admin: three pages and the JSON.
    client.get("/dev-login", params={"user_id": "admin"}, follow_redirects=False)
    for path, marker in (
        ("/admin/dashboard", "New people per day"),
        ("/admin/dashboard/people", "Reels per person"),
        ("/admin/dashboard/bot", "People who wrote per day"),
    ):
        res = client.get(path)
        check(f"admin sees {path}", res.status_code == 200 and marker in res.text, str(res.status_code))
        check(f"{path} is not cached", "no-store" in res.headers.get("cache-control", ""))
    data = client.get("/admin/dashboard.json").json()
    check("admin gets the JSON", "people" in data and "buckets" in data)

    # 4. Numbers on the sample data.
    got = {b["label"]: b["people"] for b in data["buckets"]}
    check("bucket counts are exactly right", got == EXPECTED_BUCKETS, f"{got}")
    p = data["people"]
    check("people total counts bot accounts only", p["total"] == 7, str(p["total"]))
    check("older accounts reported", data["older"] == {"people": 2, "reels": 3}, str(data["older"]))
    check("guests vs signed in", (p["guests"], p["signed_in"]) == (7, 0), f"{p['guests']}/{p['signed_in']}")
    check("new today counts the guest who joined today", p["today"] == 1, str(p["today"]))
    check("new in last 7 days", p["last_7"] == 3, str(p["last_7"]))
    r = data["reels"]
    check("reels total, bot accounts only", r["total"] == 99, str(r["total"]))
    check("failed reels", r["failed"] == 2, str(r["failed"]))
    check("cap: the 50-reel person is at the cap", data["cap"]["at_cap"] == 1, str(data["cap"]))
    check("cost at Rs 0.82", abs(data["cost"]["total"] - round(99 * 0.82, 2)) < 0.01, str(data["cost"]["total"]))
    ad = data["bot"]["ad"]
    check("ad question counted", ad["m26_ad_free"]["total"] == 1 and ad["m24_ad_hello"]["total"] == 1)
    check("waiting for a human", data["bot"]["waiting_for_human_7d"] == 1)

    res = client.get("/admin/dashboard/people")
    named = data["cap"]["at_cap_people"]
    check("cap: the person at the cap is named with a link", [(x["handle"], x["url"], x["reels"]) for x in named] == [("cap_tester", "https://www.instagram.com/cap_tester/", 50)], str(named))
    check("people page lists who is at the cap", "Who is at the cap" in res.text and 'href="https://www.instagram.com/cap_tester/"' in res.text and "@cap_tester" in res.text)
    check("people page shows Who stays", "Who stays" in res.text and "Back after 3 days" in res.text)
    check("people page links to Heavy savers", 'href="/admin/dashboard/savers"' in res.text)
    check("ad copies counted separately", data["ad_items"] == 1, str(data["ad_items"]))

    # 4a. Features tab: new people per feature, older accounts left out.
    with get_connection() as c:
        c.execute("INSERT INTO search_queries (user_id, query, created_at, updated_at) VALUES ('user_ig_2', 'cafe', ?, ?)", (iso(NOW), iso(NOW)))
        c.execute("INSERT INTO search_queries (user_id, query, created_at, updated_at) VALUES ('admin', 'cafe', ?, ?)", (iso(NOW), iso(NOW)))
        c.execute("INSERT INTO user_folders (user_id, name, created_at, updated_at) VALUES ('user_ig_3', 'Cafes', ?, ?)", (iso(NOW), iso(NOW)))
    from app.services.admin_stats import feature_usage

    with get_connection() as c:
        fu = feature_usage(c)
    by = {x["key"]: x for x in fu["rows"]}
    check("features: deep search counts new people only", by["search"]["people"] == 1, str(by["search"]))
    check("features: smart list counted", by["list"]["people"] == 1 and by["list"]["week"] == 1, str(by["list"]))
    res = client.get("/admin/dashboard/features")
    check("admin sees the Features tab", res.status_code == 200 and "People per feature" in res.text and "Deep search" in res.text and "Smart list" in res.text, str(res.status_code))

    # 4a2. Messages tab: what the bot answers is hidden, the rest shows.
    from app.services.dm_messages import bot_answers

    for words, hide in (("How does it work?", True), ("is it free", True), ("Tapped: I want to share a reel", True), ("hi", True), ("Thank you!", True),
                        ("can i save youtube videos too?", False), ("delete my data", False), ("[voice note]", False)):
        check(f"messages: {words!r} {'hidden' if hide else 'shown'}", bot_answers(words) is hide)
    with get_connection() as c:
        for i, w in enumerate(("How does it work?", "my reel is not showing")):
            c.execute("INSERT INTO instagram_webhook_events (received_at, kind, sender_id, outcome, detail) VALUES (?, 'said', 'msg_person', 'said', ?)", (iso(NOW - timedelta(minutes=5 - i)), w))
    res = client.get("/admin/dashboard/messages")
    check("messages tab hides what the bot answers", "my reel is not showing" in res.text and "How does it work?" not in res.text and "1 hidden" in res.text)
    res = client.get("/admin/dashboard/messages", params={"all": 1})
    check("messages tab shows everything on ask", "How does it work?" in res.text)

    # 4b. Who stays: cohort math on hand-made days.
    from app.services.admin_stats import cohorts

    today = "2026-10-18"
    st = cohorts(
        {
            "a": {"2026-10-14", "2026-10-15"},          # joined 14th, back on day 1 only
            "b": {"2026-10-14", "2026-10-17"},          # joined 14th, back on day 3
            "c": {"2026-10-14"},                         # joined 14th, never back
            "d": {"2026-10-17", "2026-10-18"},          # joined yesterday, back today
            "e": {"2026-10-18"},                         # joined today
            "f": set(),                                  # never sent a reel
        },
        today,
    )
    rows = {x["day"]: x for x in st["rows"]}
    check("cohort: day-1 return counts", rows["2026-10-14"]["day1"] == 2, str(rows["2026-10-14"]))
    check("cohort: day-3 return counts only day 3 or later", rows["2026-10-14"]["day3"] == 1, str(rows["2026-10-14"]))
    check("cohort: yesterday has day 1 but no day 3 yet", rows["2026-10-17"]["day1"] == 1 and rows["2026-10-17"]["day3"] is None, str(rows["2026-10-17"]))
    check("cohort: joined today is in neither", rows["2026-10-18"]["day1"] is None and rows["2026-10-18"]["day3"] is None, str(rows["2026-10-18"]))
    check("cohort: no reel means no cohort", sum(x["joined"] for x in st["rows"]) == 5)
    check("cohort: yesterday's day 1 is marked so far", rows["2026-10-17"]["day1_so_far"] is True)
    check("cohort: overall day 1 only uses finished days, 2 of 3", (st["d1_stayed"], st["d1_people"]) == (2, 3), str(st))
    check("cohort: overall day 3 is 1 of 3", (st["d3_stayed"], st["d3_people"]) == (1, 3), str(st))

    # 5. The daily bot history was seeded from the log, before any trim.
    wrote_5_days_ago = data["bot"]["wrote_per_day"][-6]
    check("seed kept 7 distinct senders from 5 days ago", wrote_5_days_ago == 7, str(wrote_5_days_ago))
    check("seed counted saved reels", data["bot"]["totals"]["saved"] == 230, str(data["bot"]["totals"]["saved"]))

    # 6. Now a webhook row gets logged, the log trims to 200, the counters keep everything.
    from app.api.routes.instagram import _log_webhook_event

    _log_webhook_event("reel", sender_id="brand_new", outcome="saved", detail="x")
    with get_connection() as c:
        kept = c.execute("SELECT COUNT(*) FROM instagram_webhook_events WHERE outcome = 'saved'").fetchone()[0]
    check("webhook log trimmed to 200", kept <= 200, str(kept))
    data = client.get("/admin/dashboard.json", params={"fresh": 1}).json()
    from app.services.admin_stats import dashboard_data

    data = dashboard_data(force=True)
    check("today's counter grew by one sender", data["bot"]["wrote_per_day"][-1] == 2, str(data["bot"]["wrote_per_day"][-1]))
    check("saved total grew by one", data["bot"]["totals"]["saved"] == 231, str(data["bot"]["totals"]["saved"]))
    check("history from 5 days ago survived the trim", data["bot"]["wrote_per_day"][-6] == 7, str(data["bot"]["wrote_per_day"][-6]))

    # 7. The button: admin profile data flags admin, the You screen shows the row only then.
    you = (ROOT / "app/static/app-v2/js/screens/you.js").read_text()
    check("You screen has the Dashboard row behind the admin flag", "u.is_admin ?" in you and 'href="/admin/dashboard"' in you)
    check("replica copy matches", 'href="/admin/dashboard"' in (ROOT / "design-explorations/app-v2/js/screens/you.js").read_text())

print()
if failures:
    print(f"{len(failures)} FAILED: " + ", ".join(failures))
    sys.exit(1)
print("ALL PASSED")
