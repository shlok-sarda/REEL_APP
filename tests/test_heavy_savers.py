"""Checks for the Heavy savers tab. Plain python, no pytest needed:

    python3 tests/test_heavy_savers.py

Runs the app against a throwaway database, then checks: only the admin can
see the tab or tick a box, people sort by today then total, ad and failed
reels do not count, core and test accounts are never block candidates, and a
tick saves and can be undone.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

work = Path(tempfile.mkdtemp(prefix="savers_test_"))
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


# id, handle, joined, reels today, reels earlier
PEOPLE = [
    ("user_ig_a", "big_total", "2026-10-16T10:00:00+00:00", 1, 40),
    ("user_ig_b", "busy_today", "2026-10-18T10:00:00+00:00", 9, 2),
    ("user_ig_c", "also_today", "2026-10-18T10:00:00+00:00", 9, 5),
    ("user_ig_d", "_.scootyyyy", "2026-10-14T18:00:00+00:00", 3, 3),   # family, keep
    ("user_ig_e", "url_testing", "2026-09-29T07:00:00+00:00", 5, 5),   # test account
    ("user_ig_f", "early_ig", "2026-10-10T07:00:00+00:00", 2, 2),      # before 14 Oct: core
]
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def seed() -> None:
    with get_connection() as c:
        c.execute("INSERT INTO users (id, display_name, email, google_sub, created_at) VALUES ('admin', 'Admin', 'admin@test.local', 'admin_sub', ?)", (iso(NOW - timedelta(days=90)),))
        c.execute("INSERT INTO users (id, display_name, email, google_sub, created_at) VALUES ('plain', 'Rohan Khatri', 'plain@test.local', 'plain_sub', '2026-07-17T20:45:33+00:00')")
        c.execute("INSERT INTO reels (id, user_id, url, shortcode, received_at, status, created_at, updated_at) VALUES ('core_r', 'plain', 'u', 's', ?, 'completed', ?, ?)", (iso(NOW), iso(NOW), iso(NOW)))
        for uid, handle, joined, today, earlier in PEOPLE:
            c.execute(
                "INSERT INTO users (id, display_name, instagram_username, created_at) VALUES (?, ?, ?, ?)",
                (uid, "Name " + handle, handle, joined),
            )
            for i in range(today + earlier):
                when = NOW - timedelta(minutes=i) if i < today else NOW - timedelta(days=3, minutes=i)
                c.execute(
                    "INSERT INTO reels (id, user_id, url, shortcode, received_at, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)",
                    (f"{uid}_r{i}", uid, f"https://www.instagram.com/reel/{uid}{i}/", f"{uid}{i}", iso(when), iso(when), iso(when)),
                )
        # Neither our own ad reel nor a failed reel counts.
        c.execute("INSERT INTO reels (id, user_id, url, shortcode, received_at, status, source, created_at, updated_at) VALUES ('ad', 'user_ig_a', 'u_ad', 'ad', ?, 'completed', 'clipnest_ad', ?, ?)", (iso(NOW), iso(NOW), iso(NOW)))
        c.execute("INSERT INTO reels (id, user_id, url, shortcode, received_at, status, created_at, updated_at) VALUES ('bad', 'user_ig_a', 'u_bad', 'bad', ?, 'failed', ?, ?)", (iso(NOW), iso(NOW), iso(NOW)))


with TestClient(app, client=("127.0.0.1", 50000)) as client:
    seed()
    res = client.get("/admin/dashboard/savers")
    check("logged out gets 404", res.status_code == 404, str(res.status_code))
    res = client.post("/admin/dashboard/savers/cross", data={"user_id": "user_ig_b", "crossed": "1"})
    check("logged out cannot tick", res.status_code == 404, str(res.status_code))
    client.get("/dev-login", params={"user_id": "plain"}, follow_redirects=False)
    check("non-admin gets 404", client.get("/admin/dashboard/savers").status_code == 404)

    client.get("/dev-login", params={"user_id": "admin"}, follow_redirects=False)
    res = client.get("/admin/dashboard/savers")
    check("admin sees the tab", res.status_code == 200 and "Heavy savers" in res.text, str(res.status_code))
    check("tab is in the nav on every page", 'href="/admin/dashboard/savers"' in client.get("/admin/dashboard").text)
    html = res.text
    order = [h for h in ("also_today", "busy_today", "big_total") if h in html]
    pos = [html.index("@" + h) for h in order]
    check("sorted by today, then total", order == ["also_today", "busy_today", "big_total"] and pos == sorted(pos), str(pos))
    check("handle opens Instagram in a new tab", 'href="https://www.instagram.com/busy_today/" target="_blank"' in html)
    check("test account left out", "url_testing" not in html)
    check("Google core user left out", "Rohan Khatri" not in html)

    from app.services.heavy_savers import heavy_savers

    with get_connection() as c:
        people = {p["handle"]: p for p in heavy_savers(c)["people"]}
    check("ad and failed reels not counted", (people["big_total"]["today"], people["big_total"]["total"]) == (1, 41), str(people["big_total"]))
    check("family handle marked core", people["_.scootyyyy"]["core"])
    check("account from before 14 Oct marked core", people["early_ig"]["core"])
    check("new account is a candidate", not people["busy_today"]["core"])
    keep_rows = [line for line in html.split("<tr") if "@_.scootyyyy" in line or "@early_ig" in line]
    check("core rows say core, keep and have no box", len(keep_rows) == 2 and all("core, keep" in r and "<form" not in r for r in keep_rows))

    res = client.post("/admin/dashboard/savers/cross", data={"user_id": "user_ig_b", "crossed": "1"}, follow_redirects=False)
    check("tick redirects back to the row", res.status_code == 303 and res.headers["location"].endswith("#user_ig_b"), str(res.status_code))
    html = client.get("/admin/dashboard/savers").text
    check("ticked person shows blocked by me", "blocked by me" in html and "Blocked by me</h2>" in html)
    check("tick survives a reload", 'class="tick on"' in html)
    client.post("/admin/dashboard/savers/cross", data={"user_id": "user_ig_d", "crossed": "1"})
    with get_connection() as c:
        people = {p["handle"]: p for p in heavy_savers(c)["people"]}
    check("a core person can never be crossed off", not people["_.scootyyyy"]["crossed"])
    client.post("/admin/dashboard/savers/cross", data={"user_id": "user_ig_b", "crossed": "0"})
    check("untick works", 'class="tick on"' not in client.get("/admin/dashboard/savers").text)
    res = client.post("/admin/dashboard/savers/cross", data={"user_id": "plain", "crossed": "1"})
    check("only Instagram accounts can be ticked", res.status_code == 400, str(res.status_code))
    with get_connection() as c:
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    check("ticking never removes anyone", users == 2 + len(PEOPLE) + 1, str(users))

print()
if failures:
    print(f"{len(failures)} FAILED: " + ", ".join(failures))
    sys.exit(1)
print("ALL PASSED")
