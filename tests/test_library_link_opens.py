"""Checks that opening a /g/<token> library link is recorded. Plain python:

    python3 tests/test_library_link_opens.py

A person opening their link counts; Instagram's link preview bot does not; the
first open time stays put while the count and last open move; and the admin
Bot page splits people who got the link into opened and never opened.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

work = Path(tempfile.mkdtemp(prefix="opens_test_"))
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
        "DASHBOARD_LINK_OPENS_FROM": "2026-01-01 00:00:00",
    }
)

from starlette.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db.database import get_connection  # noqa: E402
from app.db.init_db import initialize_database  # noqa: E402
from app.services.auth import get_or_create_library_token  # noqa: E402

initialize_database()

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")
OLD = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat(timespec="seconds")
with get_connection() as c:
    for uid, sent in (("user_ig_a", NOW), ("user_ig_b", NOW), ("user_ig_old", OLD)):
        c.execute("INSERT INTO users (id, display_name, created_at) VALUES (?, ?, ?)", (uid, uid, NOW))
        c.execute("INSERT INTO nudge_log (user_id, message_key, sent_at) VALUES (?, 'm2_first_library', ?)", (uid, sent))

token_a = get_or_create_library_token("user_ig_a")
client = TestClient(app)
IG = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 350.0.0"
BOT = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"


def opens(uid: str):
    with get_connection() as c:
        return c.execute("SELECT library_opened_at, library_last_opened_at, library_opens FROM users WHERE id = ?", (uid,)).fetchone()


r = client.get(f"/g/{token_a}", headers={"user-agent": BOT})
check("preview bot still gets the page", r.status_code == 200, str(r.status_code))
check("preview bot is not counted", opens("user_ig_a")["library_opens"] == 0)

r = client.get(f"/g/{token_a}", headers={"user-agent": IG})
first = opens("user_ig_a")
check("a person opening the link is counted", r.status_code == 200 and first["library_opens"] == 1 and first["library_opened_at"] != "", str(dict(first)))

client.get(f"/g/{token_a}", headers={"user-agent": IG})
second = opens("user_ig_a")
check("second open adds one, first time stays", second["library_opens"] == 2 and second["library_opened_at"] == first["library_opened_at"], str(dict(second)))

client.get("/g/not-a-real-token-at-all-xxxxxxxxxxxx", headers={"user-agent": IG})
check("unknown token records nothing", opens("user_ig_b")["library_opens"] == 0)

from app.services.admin_stats import dashboard_data  # noqa: E402

lo = dashboard_data(force=True)["bot"]["link_opens"]
check("got the link counts only links sent since counting began", lo["got"] == 2, str(lo))
check("opened and never opened split", lo["opened"] == 1 and lo["never"] == 1, str(lo))
check("opened today", lo["opened_today"] == 1, str(lo))

print()
if failures:
    print(f"{len(failures)} FAILED: " + ", ".join(failures))
    sys.exit(1)
print("ALL PASSED")
