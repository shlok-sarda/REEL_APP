"""Checks for the reels sent versus saved counter. Plain python, no pytest:

    python3 tests/test_reel_counter.py

Posts real-shaped Instagram deliveries at the webhook against a throwaway
database and checks the counter: a delivery Meta sends twice counts once, a
reel already in the library is a duplicate and not a second save, a feed
share with no link counts as sent and not saved (no link), a finished reel
counts as saved, our own ad reel is not one of theirs, and a counter that
breaks never stops the reel from saving.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

work = Path(tempfile.mkdtemp(prefix="reel_counter_test_"))
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{work / 'app.db'}",
        "STORAGE_DIR": str(work / "st"),
        "MEDIA_DIR": str(work / "md"),
        "QUEUE_JANITOR": "off",
        "APP_ENV": "development",
        "SESSION_SECRET": "counter-test",
        "PUBLIC_BASE_URL": "http://127.0.0.1:8017",
        "ADMIN_EMAILS": "admin@test.local",
        "GUEST_AUTOCREATE_FOR_EVERYONE": "1",
        "DM_REPLY_FOR_EVERYONE": "1",
        "GUEST_LOCK_ENABLED": "0",
        "OUTBOUND_DM_TEST": "0",
        "INSTAGRAM_APP_SECRET": "",
        "INSTAGRAM_ACCESS_TOKEN": "",
        "INSTAGRAM_APP_USERNAME": "clipnest.in",
        "OPENAI_API_KEY": "sk-disabled-local-test",
        "APIFY_TOKEN": "",
    }
)

from starlette.testclient import TestClient  # noqa: E402

from app.api.routes import instagram as route  # noqa: E402
from app.db.database import get_connection  # noqa: E402
from app.main import app  # noqa: E402
from app.services import admin_stats, nudge, reel_counter  # noqa: E402

# Nothing leaves the machine: no sends, no worker, no Graph lookups.
nudge.fire = lambda *a, **k: ""
route._reply_later = lambda func, *args: None
# Replies are dropped; a post with no link is counted after the settle wait,
# so that one runs at once.
route._settle_then = lambda func, *args: func(*args) if func is route._record_post_later else None
route.fill_username_for_sender = lambda sender_id: None
route.ensure_background_progress = lambda: None
route.own_media._known = lambda: ({"17900000000000001"}, {"ADREEL0001"})
route.own_media._look_up = lambda media_id: ""

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def body(sender: str, mid: str, **message) -> dict:
    return {"object": "instagram", "entry": [{"id": "biz", "time": 1, "messaging": [
        {"sender": {"id": sender}, "recipient": {"id": "biz"}, "timestamp": 1, "message": {"mid": mid, **message}}
    ]}]}


def reel_link(code: str) -> str:
    return f"https://www.instagram.com/reel/{code}/"


def counts() -> dict:
    admin_stats._cache["data"] = None
    return admin_stats.dashboard_data(force=True)["sent"]


def finish(code: str, status: str = "completed", error: str = "") -> None:
    """What the worker leaves behind for one reel."""
    with get_connection() as c:
        row = c.execute("SELECT id FROM reels WHERE shortcode = ? OR url LIKE ?", (code, f"%{code}%")).fetchone()
        c.execute("UPDATE reels SET status = ? WHERE id = ?", (status, row["id"]))
        if error:
            c.execute(
                "UPDATE processing_jobs SET status = 'failed', error_message = ? WHERE reel_id = ?", (error, row["id"])
            )


with TestClient(app, client=("127.0.0.1", 50000)) as client:
    with get_connection() as c:
        c.execute("DELETE FROM users WHERE id = 'default'")

    # 1. A delivery Meta sends twice (it retries when it is unsure) counts once.
    retry = body("p1", "mid_retry", text=reel_link("AAA111"))
    first = client.post("/instagram/webhook", json=retry)
    again = client.post("/instagram/webhook", json=retry)
    check("webhook answers both deliveries", first.status_code == 200 and again.status_code == 200)
    a = counts()["all"]
    check("retried delivery counts once as sent", a["received"] == 1, str(a))
    check("retried delivery is not a duplicate", a["duplicates"] == 0, str(a))
    check("queued reel is still being read", a["in_progress"] == 1 and a["processed"] == 0, str(a))

    # 2. Once the worker finishes it, it counts as saved.
    finish("AAA111")
    a = counts()["all"]
    check("finished reel counts as saved", a["processed"] == 1 and a["in_progress"] == 0, str(a))
    check("nothing missing yet, gap 0", a["gap"] == 0, str(a))

    # 3. The same reel sent again in a new message: a duplicate, not a second save.
    client.post("/instagram/webhook", json=body("p1", "mid_dup", text=reel_link("AAA111")))
    a = counts()["all"]
    check("resent reel counts as sent", a["received"] == 2, str(a))
    check("resent reel counts as duplicate", a["duplicates"] == 1, str(a))
    check("resent reel is not counted as saved twice", a["processed"] == 1, str(a))
    check("duplicate leaves no gap", a["gap"] == 0, str(a))

    # 4. The same reel from someone else counts for them too.
    client.post("/instagram/webhook", json=body("p2", "mid_p2", text=reel_link("AAA111")))
    a = counts()["all"]
    check("same reel from another person is not a duplicate", a["received"] == 3 and a["duplicates"] == 1, str(a))

    # 5. A reel shared from the feed: only the reel's number, no link.
    feed_share = [{"type": "ig_reel", "payload": {"reel_video_id": "18000000000000099", "title": "x"}}]
    client.post("/instagram/webhook", json=body("p3", "mid_feed", attachments=feed_share))
    a = counts()["all"]
    check("feed share with no link counts as sent", a["received"] == 4, str(a))
    check("feed share with no link is not saved (no link)",
          a["not_processed"] == 1 and a["reasons"]["no_link_reel"] == 1, str(a))

    # 6. A post with no link has its own reason.
    post_share = [{"type": "ig_post", "payload": {"ig_post_media_id": "18000000000000077", "url": "https://lookaside.fbsbx.com/x"}}]
    client.post("/instagram/webhook", json=body("p3", "mid_post", attachments=post_share))
    a = counts()["all"]
    check("post with no link counts with its own reason", a["reasons"]["no_link_post"] == 1, str(a))

    # 7. Our own ad reel shared back is counted on its own, not as theirs.
    client.post("/instagram/webhook", json=body("p4", "mid_ad", text=reel_link("ADREEL0001")))
    a = counts()["all"]
    check("ad reel is not counted as a sent reel", a["received"] == 5, str(a))
    check("ad reel is counted separately", a["ad"] == 1, str(a))

    # 8. A reel the worker could not fetch fails as private or deleted.
    client.post("/instagram/webhook", json=body("p5", "mid_private", text=reel_link("PRIV01")))
    finish("PRIV01", "failed", "Reel unavailable: login required")
    a = counts()["all"]
    check("private reel counts as not saved (private)", a["reasons"]["private"] == 1, str(a))
    check("gap is sent minus duplicates minus saved",
          a["gap"] == a["received"] - a["duplicates"] - a["processed"] and a["gap"] == 4, str(a))
    t = counts()["today"]
    check("today and 7 days hold the same reels as all time here",
          t["received"] == counts()["last_7"]["received"] == a["received"], str(t))

    # 8b. Queued and the day by day view.
    full = counts()
    check("queued counts the reels handed to the processing queue", full["all"]["queued"] == 3, str(full["all"]))
    today_row = full["days"][-1] if full["days"] else {}
    check("day by day has today's row", today_row.get("day") == admin_stats._today_local(), str(today_row))
    check("today's row: sent, queued, saved",
          (today_row.get("sent"), today_row.get("queued"), today_row.get("saved")) == (6, 3, 1), str(today_row))

    # 8c. A reel sent with no link but with Meta's video link is saved from
    # the video. If that save crashes, the reel is still counted as sent.
    shared = {"type": "unsupported_type", "payload": {"url": "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=777&signature=x"}}
    event = {"sender": {"id": "p7"}, "message": {"mid": "mid_shared_ok", "attachments": [shared]}}
    with get_connection() as c:
        c.execute("INSERT INTO users (id, display_name, created_at) VALUES ('user_ig_p7', 'p7', '2026-10-01T00:00:00')")
    real_download = route._download_shared_video

    def fake_download(url, target):
        target.write_bytes(b"video")
        return True

    route._download_shared_video = fake_download
    route._save_shared_video("user_ig_p7", "p7", "", shared["payload"]["url"], event)
    a = counts()["all"]
    check("shared video with no link counts as sent and queued", (a["received"], a["queued"]) == (7, 4), str(a))

    def crash(url, target):
        raise RuntimeError("disk gone")

    route._download_shared_video = crash
    crashed_event = {"sender": {"id": "p7"}, "message": {"mid": "mid_shared_crash", "attachments": [shared]}}
    try:
        route._save_shared_video("user_ig_p7", "p7", "", shared["payload"]["url"].replace("777", "778"), crashed_event)
    except RuntimeError:
        pass
    route._download_shared_video = real_download
    a = counts()["all"]
    check("shared video save that crashes still counts as sent (our error)",
          a["received"] == 8 and a["reasons"]["our_error"] == 1, str(a))

    # 9. A counter that breaks must never stop the reel from saving.
    real = reel_counter.get_connection

    def broken():
        raise RuntimeError("counter table gone")

    reel_counter.get_connection = broken
    res = client.post("/instagram/webhook", json=body("p6", "mid_broken", text=reel_link("SAFE01")))
    reel_counter.get_connection = real
    with get_connection() as c:
        saved = c.execute("SELECT COUNT(*) FROM reels WHERE url LIKE '%SAFE01%'").fetchone()[0]
    check("broken counter: webhook still answers 200", res.status_code == 200, str(res.status_code))
    check("broken counter: reel still saved", saved == 1, str(saved))

    # 10. The card on the Today page.
    with get_connection() as c:
        c.execute(
            "INSERT OR IGNORE INTO users (id, display_name, email, google_sub, created_at) VALUES ('admin', 'admin', 'admin@test.local', 'admin_sub', '2026-01-01T00:00:00')"
        )
    client.get("/dev-login", params={"user_id": "admin"}, follow_redirects=False)
    page = client.get("/admin/dashboard")
    check("Today page shows the card", page.status_code == 200 and "Reels sent versus saved" in page.text, str(page.status_code))
    check("card carries the audit line", "Earlier totals: 217 sent, 164 saved on 18 Oct (audit)." in page.text)
    check("card shows the queue line and the day by day table",
          "Went to the processing queue" in page.text and "Day by day" in page.text)
    check("card has no long dashes", "—" not in page.text.split("Reels sent versus saved")[1].split("</section>")[0])

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("All reel counter checks passed.")
