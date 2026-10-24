"""Checks that the database copy to R2 happens about every hour. Plain
python, no pytest:

    python3 tests/test_db_backup_hourly.py

Measured miss this guards: the janitor only asked for a copy once after boot
and then every 144th tick (about 6 hours), so latest.db.gz looked stuck for
hours. Uploads are faked; nothing leaves the machine.
"""
from __future__ import annotations

import gzip
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

work = Path(tempfile.mkdtemp(prefix="db_backup_test_"))
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{work / 'app.db'}",
        "STORAGE_DIR": str(work / "st"),
        "MEDIA_DIR": str(work / "md"),
        "QUEUE_JANITOR": "off",
        "APP_ENV": "development",
        "SESSION_SECRET": "backup-test",
        "OPENAI_API_KEY": "sk-disabled-local-test",
        "R2_BUCKET_NAME": "test-bucket",
        "R2_ACCOUNT_ID": "test",
        "R2_ENDPOINT": "http://127.0.0.1:1",
        "R2_ACCESS_KEY_ID": "test",
        "R2_SECRET_ACCESS_KEY": "test",
    }
)

from app import main  # noqa: E402
from app.db.database import get_connection  # noqa: E402
from app.db.init_db import initialize_database  # noqa: E402
from app.services import db_backup  # noqa: E402

initialize_database()

uploads: list[str] = []


def fake_upload(path, key, content_type=None):
    with gzip.open(path, "rb") as packed:
        assert packed.read(16).startswith(b"SQLite format 3"), "copy is not a database"
    uploads.append(key)
    return True


db_backup.upload_file = fake_upload
failures = 0


def check(name, ok):
    global failures
    print(("PASS " if ok else "FAIL ") + name)
    failures += 0 if ok else 1


def set_last(minutes_ago):
    stamp = (datetime.now() - timedelta(minutes=minutes_ago)).isoformat(timespec="seconds")
    with get_connection() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO maintenance_flags (flag, executed_at) VALUES (?, ?)",
            (db_backup.BACKUP_FLAG, stamp),
        )


first = db_backup.backup_database()
check("first copy uploads latest.db.gz", first.get("ok") and "backups/app.db/latest.db.gz" in uploads)
check("copy is recorded for /health", db_backup.last_backup_at() == first.get("at"))

uploads.clear()
again = db_backup.backup_database()
check("a second ask right away is skipped", again.get("skipped") and not uploads)

set_last(30)
check("30 minutes later is still skipped", db_backup.backup_database().get("skipped") and not uploads)

set_last(56)
later = db_backup.backup_database()
check("56 minutes later makes a new copy", later.get("ok") and not later.get("skipped") and uploads)

# The janitor must ask on every tick, not every 144th.
asked = []
ticks = {"n": 0}


class Stop(Exception):
    pass


def fake_sleep(seconds):
    if seconds == 150:
        ticks["n"] += 1
        if ticks["n"] >= 5:
            raise Stop


main.time.sleep = fake_sleep
import subprocess  # noqa: E402

subprocess.Popen = lambda *a, **k: None
from app.services import instagram_token, jobs, nudge  # noqa: E402

jobs.ensure_background_progress = lambda: None
jobs.maybe_spawn_media_repair = lambda: None
nudge.run_last_call_sweep = lambda: None
instagram_token.maybe_refresh = lambda: None
db_backup.backup_database = lambda force=False: asked.append(1) or {"ok": True, "skipped": "x"}
try:
    main._queue_janitor_loop()
except Stop:
    pass
check("janitor asks for a backup on every tick", len(asked) == 5)

# A failed copy waits 15 minutes before retrying instead of every tick.
asked.clear()
ticks["n"] = 0
db_backup.backup_database = lambda force=False: asked.append(1) or {"ok": False, "reason": "upload refused"}
try:
    main._queue_janitor_loop()
except Stop:
    pass
check("a failure is not retried on every tick", len(asked) == 1)

print("ALL PASS" if not failures else f"{failures} FAILED")
sys.exit(1 if failures else 0)
