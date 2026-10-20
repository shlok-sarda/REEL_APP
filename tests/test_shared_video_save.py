"""A reel Instagram sends with no link is saved from Meta's media link.
Plain python:

    python3 tests/test_shared_video_save.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

work = Path(tempfile.mkdtemp(prefix="share_test_"))
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{work / 'app.db'}",
        "STORAGE_DIR": str(work / "st"),
        "MEDIA_DIR": str(work / "media"),
        "QUEUE_JANITOR": "off",
        "DM_REPLY_FOR_EVERYONE": "1",
        "INSTAGRAM_APP_SECRET": "",
    }
)

import requests  # noqa: E402

from app.db.init_db import initialize_database  # noqa: E402

initialize_database()

from app.api.routes import instagram as ig  # noqa: E402
from app.db.database import get_connection  # noqa: E402
from app.services import nudge  # noqa: E402

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f" :: {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)


class FakeResp:
    def __init__(self, status: int, kind: str, body: bytes):
        self.status_code, self.headers, self._body = status, {"Content-Type": kind}, body

    def iter_content(self, chunk_size=1):
        yield self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


asked: list[str] = []
serve = {"resp": FakeResp(200, "video/mp4", b"\x00\x00\x00 ftypisom" + b"x" * 1000)}


def fake_get(url, **kw):
    asked.append(url)
    return serve["resp"]


requests.get = fake_get
fired: list[tuple[str, str]] = []
nudge.fire = lambda user_id, trigger, *a, **k: fired.append((user_id, trigger)) or trigger
ig.ensure_background_progress = lambda: None

USER = "user_ig_test1"
with get_connection() as c:
    c.execute(
        "INSERT INTO users (id, display_name, created_at, updated_at, instagram_user_id) VALUES (?, 'T', '2026-10-20', '2026-10-20', 'igs1')",
        (USER,),
    )

MEDIA = "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=987654321&signature=abc"
event = {"sender": {"id": "igs1"}, "message": {"mid": "m1", "attachments": [{"type": "unsupported_type", "payload": {"url": MEDIA}}]}}

check("finds Meta's media link", ig._shared_video_link(event) == MEDIA)
check("ignores any other host", ig._shared_video_link({"message": {"attachments": [{"type": "unsupported_type", "payload": {"url": "https://evil.example/x"}}]}}) == "")
check("ignores http", ig._shared_video_link({"message": {"attachments": [{"type": "unsupported_type", "payload": {"url": MEDIA.replace("https", "http")}}]}}) == "")

ig._save_shared_video(USER, "igs1", "t", MEDIA, event)
with get_connection() as c:
    rows = [dict(r) for r in c.execute("SELECT id, url, local_video_path, media_status FROM reels WHERE user_id = ?", (USER,))]
    jobs = c.execute("SELECT COUNT(*) FROM processing_jobs").fetchone()[0]
check("one reel saved", len(rows) == 1, str(rows))
row = rows[0] if rows else {}
check("stored under the asset id", row.get("url") == "https://www.instagram.com/reel/share_987654321/", row.get("url", ""))
check("video on disk", bool(row.get("local_video_path")) and Path(row["local_video_path"]).stat().st_size > 1000)
check("media ready", row.get("media_status") == "ready", row.get("media_status", ""))
check("job queued", jobs == 1, str(jobs))
check("answered like a saved reel", fired[-1] == (USER, "reel_saved"), str(fired))
check("only Meta's host was asked", asked == [MEDIA], str(asked))

with get_connection() as c:
    c.execute("UPDATE reels SET status = 'completed' WHERE user_id = ?", (USER,))
ig._save_shared_video(USER, "igs1", "t", MEDIA, event)
check("same share again is already saved", fired[-1] == (USER, "already_saved"), str(fired))

serve["resp"] = FakeResp(200, "image/jpeg", b"jpeg")
OTHER = MEDIA.replace("987654321", "111")
ig._save_shared_video(USER, "igs1", "t", OTHER, event)
with get_connection() as c:
    n = c.execute("SELECT COUNT(*) FROM reels WHERE user_id = ?", (USER,)).fetchone()[0]
check("not a video: nothing saved", n == 1, str(n))
check("not a video: told to copy the link", fired[-1] == (USER, "unreadable_share"), str(fired))

serve["resp"] = FakeResp(403, "text/html", b"no")
ig._save_shared_video(USER, "igs1", "t", OTHER, event)
check("expired link: told to copy the link", fired[-1] == (USER, "unreadable_share"), str(fired))

# Through the webhook: the share goes to the save path, not the copy-link reply.
ig._reply_later = lambda func, *args: func(*args)
ig._settle_then = lambda func, *args: fired.append(("settle", args[-1]))
serve["resp"] = FakeResp(200, "video/mp4", b"\x00\x00\x00 ftypisom" + b"y" * 1000)
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

THIRD = MEDIA.replace("987654321", "222333")
body = {"object": "instagram", "entry": [{"id": "page", "time": 1, "messaging": [
    {"sender": {"id": "igs1"}, "recipient": {"id": "page"}, "timestamp": 1,
     "message": {"mid": "m3", "attachments": [{"type": "unsupported_type", "payload": {"url": THIRD}}]}}]}]}
resp = TestClient(app).post("/instagram/webhook", content=json.dumps(body), headers={"Content-Type": "application/json"})
check("webhook accepted", resp.status_code == 200, str(resp.status_code))
with get_connection() as c:
    got = c.execute("SELECT COUNT(*) FROM reels WHERE url = 'https://www.instagram.com/reel/share_222333/'").fetchone()[0]
check("webhook share saved", got == 1, f"{got} fired={fired[-3:]}")
check("no copy-link reply for it", ("settle", "unreadable_share") not in fired, str(fired[-3:]))

print()
print("ALL PASS" if not failures else f"{len(failures)} FAILED")
sys.exit(1 if failures else 0)
