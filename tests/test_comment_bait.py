"""Checks for the "comment LINK to get the link" tagger. Plain python:

    python3 tests/test_comment_bait.py

Covers the detector on clear hits and clear misses, a reel with no text, a
/p/ post being skipped, the backfill, the worker never failing on it, and the
admin list (404 for everyone else, no user data in it).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

work = Path(tempfile.mkdtemp(prefix="bait_test_"))
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{work / 'app.db'}",
        "STORAGE_DIR": str(work / "st"),
        "MEDIA_DIR": str(work / "md"),
        "QUEUE_JANITOR": "off",
        "APP_ENV": "development",
        "PUBLIC_BASE_URL": "http://127.0.0.1:8018",
        "ADMIN_EMAILS": "admin@test.local",
        "OPENAI_API_KEY": "sk-disabled-local-test",
        "APIFY_TOKEN": "",
    }
)

from app.db.database import get_connection  # noqa: E402
from app.db.init_db import initialize_database  # noqa: E402
from app.services import comment_bait  # noqa: E402

initialize_database()

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def hit(text: str, source: str = "caption"):
    return comment_bait.detect({source: text})


# --- Clear hits ---------------------------------------------------------------
HITS = [
    ("Comment LINK and I'll send it to your DMs", "LINK", "link"),
    ("Want this top? comment link for the link", "LINK", "link"),
    ("Type RECIPE below and I'll send you the full recipe", "RECIPE", "recipe"),
    ("type 'recipe' in the comments", "RECIPE", "recipe"),
    ("DM me PDF to get the full guide", "PDF", "file"),
    ("DM me \"SHOES\" for the link", "SHOES", "link"),
    ("Comment “GUIDE” to get my free travel guide", "GUIDE", "file"),
    ("Comment the word YES and I'll send you the link", "YES", "link") if False else
    ("Comment the word GLOW and I'll send you the link", "GLOW", "link"),
    ("Comment CODE for 20% off", "CODE", "code"),
    ("comment SALE and I will DM you the discount code", "SALE", "code"),
    ("Recipe chahiye? RECIPE comment karo, main bhej dunga", "RECIPE", "recipe"),
    ("link comment karo aur link mil jayega", "LINK", "link"),
    ("comment mein PLAN likho, DM mein bhej dunga", "PLAN", "file"),
    ("Comment LIST to get all 10 cafes", "LIST", "list"),
    ("Comment for the recipe", "ANY", "recipe"),
]
for text, trigger, promise in HITS:
    got = hit(text)
    check(f"hit: {text!r}", bool(got) and got["trigger"] == trigger and got["promise"] == promise, str(got))

got = hit("so if you want this, just comment link and I'll send it", source="transcript")
check("hit in transcript keeps its source", bool(got) and got["source"] == "transcript", str(got))

# --- Clear misses -------------------------------------------------------------
MISSES = [
    "Comment below!",
    "comment your favourite",
    "Comment your thoughts below",
    "Comment YES if you agree",
    "Let me know in the comments what you think",
    "Link in bio",
    "Check the pinned comment, link is there",
    "the first comment link has it",
    "this type of recipe is my favourite",
    "Drop a like and follow for more",
    "DM me for collabs",
    "comment karo aur share karo",
    "Comment who you'd take here",
    "FOLLOW FOR MORE RECIPES. COMMENT BELOW YOUR FAVOURITE",
    "send me your photos",
    "",
]
for text in MISSES:
    got = hit(text)
    check(f"miss: {text!r}", got is None, str(got))

check("reel with no text at all", comment_bait.detect({"caption": "", "transcript": None, "on_screen": []}) is None)

# --- Stored tags, backfill, posts skipped ---------------------------------------
NOW = datetime.now().isoformat(timespec="seconds")
REELS = {
    "reel_1": ("https://www.instagram.com/reel/AAA/", {"caption": "Comment LINK to get the link", "transcript": ""}),
    "reel_2": ("https://www.instagram.com/reel/BBB/", {"caption": "Comment below your favourite", "transcript": ""}),
    "reel_3": ("https://www.instagram.com/p/CCC/", {"caption": "Comment GUIDE to get my guide"}),
    "reel_4": ("https://www.instagram.com/reel/DDD/", None),
    "reel_5": ("https://www.instagram.com/reel/AAA/?igsh=x", {"caption": "Comment LINK to get the link"}),
}
with get_connection() as c:
    c.execute("INSERT OR IGNORE INTO users (id, display_name, created_at) VALUES ('u1', 'Secret Person', ?)", (NOW,))
    c.execute("INSERT OR IGNORE INTO users (id, display_name, created_at) VALUES ('u2', 'Other Person', ?)", (NOW,))
    for i, (rid, (url, meta)) in enumerate(REELS.items()):
        owner = "u2" if rid == "reel_5" else "u1"
        c.execute(
            "INSERT INTO reels (id, user_id, url, received_at, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'completed', ?, ?)",
            (rid, owner, url, NOW, NOW, NOW),
        )
        if meta is not None:
            c.execute(
                "INSERT INTO reel_processing_diagnostics (reel_id, user_id, url, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (rid, owner, url, json.dumps(meta), NOW, NOW),
            )
    c.execute("INSERT INTO reel_items (reel_id, item_name, created_at) VALUES ('reel_1', 'Linen shirt haul', ?)", (NOW,))

result = comment_bait.backfill()
check("backfill scans every reel", result["scanned"] == 5, str(result))
check("backfill tags the two real hits only", result["tagged"] == 2, str(result))
with get_connection() as c:
    tagged = {r["reel_id"] for r in c.execute("SELECT reel_id FROM comment_bait_reels")}
check("a /p/ post is never tagged", "reel_3" not in tagged, str(tagged))
check("a reel with no extracted text is not tagged", "reel_4" not in tagged, str(tagged))

first = comment_bait.backfill_once()
second = comment_bait.backfill_once()
check("startup backfill runs once per version", isinstance(first, dict) and second == "", f"{first} / {second}")

rows = comment_bait.list_tagged()
check("same reel saved twice is one row", len(rows) == 1 and rows[0]["saves"] == 2, str(rows))
check("list carries the title", rows and rows[0]["title"] == "Linen shirt haul", str(rows))

# Tag a single new reel the way the worker does, and one that is missing.
with get_connection() as c:
    c.execute(
        "UPDATE reel_processing_diagnostics SET metadata_json = ? WHERE reel_id = 'reel_2'",
        (json.dumps({"caption": "Type RECIPE below and I'll send it"}),),
    )
check("tag_reel tags a newly processed reel", (comment_bait.tag_reel("reel_2") or {}).get("trigger") == "RECIPE")
check("tag_reel on a missing reel returns None", comment_bait.tag_reel("reel_missing") is None)

# A broken database call must never raise out of tag_reel.
orig = comment_bait.get_connection
comment_bait.get_connection = lambda: (_ for _ in ()).throw(RuntimeError("db down"))
try:
    check("tag_reel never raises", comment_bait.tag_reel("reel_1") is None)
finally:
    comment_bait.get_connection = orig

# --- Admin page and CSV -------------------------------------------------------
from starlette.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

with get_connection() as c:
    c.execute("INSERT OR IGNORE INTO users (id, display_name, email, created_at) VALUES ('admin', 'Admin', 'admin@test.local', ?)", (NOW,))
    c.execute("INSERT OR IGNORE INTO users (id, display_name, email, created_at) VALUES ('plain', 'Plain', 'plain@test.local', ?)", (NOW,))

client = TestClient(app, client=("127.0.0.1", 50000))
for path in ("/admin/comment-reels", "/admin/comment-reels.csv"):
    check(f"logged out gets 404 on {path}", client.get(path).status_code == 404)

dev_login = client.get("/dev-login", params={"user_id": "plain"}, follow_redirects=False)
if dev_login.status_code == 303:
    check("non-admin gets 404", client.get("/admin/comment-reels").status_code == 404)
    client.cookies.clear()
    client.get("/dev-login", params={"user_id": "admin"}, follow_redirects=False)
    page = client.get("/admin/comment-reels")
    check("admin gets the list", page.status_code == 200 and "Linen shirt haul" in page.text, str(page.status_code))
    check("list shows no user names", "Secret Person" not in page.text and "Other Person" not in page.text)
    csv_resp = client.get("/admin/comment-reels.csv")
    check("admin gets the CSV", csv_resp.status_code == 200 and "LINK" in csv_resp.text, str(csv_resp.status_code))
    check("CSV has no user ids", "u1" not in csv_resp.text.replace("reel_1", ""), csv_resp.text[:200])
    dash = client.get("/admin/dashboard")
    check("dashboard links to the list", '/admin/comment-reels"' in dash.text)
else:
    check("dev-login available for the admin check", False, str(dev_login.status_code))

print()
print("ALL PASS" if not failures else f"{len(failures)} FAILED")
sys.exit(1 if failures else 0)
