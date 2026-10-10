"""Copy the SQLite database to object storage so a lost disk is not a lost product.

The whole product state is one file on one disk. This takes a consistent
snapshot with SQLite's own backup API (safe while the app is writing, WAL
included), gzips it and uploads it to the private R2 bucket. Called from the
queue janitor every few hours.
"""
from __future__ import annotations

import gzip
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.db.database import get_connection
from app.services.object_storage import upload_file

BACKUP_FLAG = "db_backup_last"
BACKUP_PREFIX = "backups/app.db"


def last_backup_at() -> str:
    try:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT executed_at FROM maintenance_flags WHERE flag = ? LIMIT 1", (BACKUP_FLAG,)
            ).fetchone()
        return row["executed_at"] if row else ""
    except Exception:
        return ""


def backup_database(force: bool = False) -> dict:
    """Snapshot, compress, upload. Returns what happened; never raises."""
    if not settings.r2_enabled:
        return {"ok": False, "reason": "object storage is not configured"}
    # A restart loop must not turn into a backup loop.
    previous = last_backup_at()
    if previous and not force:
        try:
            if (datetime.now() - datetime.fromisoformat(previous)).total_seconds() < 3600:
                return {"ok": True, "skipped": "backed up less than an hour ago", "at": previous}
        except ValueError:
            pass
    # Weekday and hour, so copies roll over after a week instead of piling up
    # forever. latest.db.gz is always the newest one.
    stamp = datetime.now().strftime("%a-%H")
    workdir = Path(tempfile.mkdtemp(prefix="db_backup_"))
    snapshot = workdir / "app.db"
    packed = workdir / "app.db.gz"
    try:
        source = sqlite3.connect(str(settings.database_path), timeout=30)
        target = sqlite3.connect(str(snapshot))
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        with snapshot.open("rb") as raw, gzip.open(packed, "wb", compresslevel=6) as zipped:
            shutil.copyfileobj(raw, zipped, length=1024 * 1024)
        size = packed.stat().st_size
        uploaded = upload_file(packed, f"{BACKUP_PREFIX}/{stamp}.db.gz", "application/gzip") and upload_file(
            packed, f"{BACKUP_PREFIX}/latest.db.gz", "application/gzip"
        )
        if not uploaded:
            return {"ok": False, "reason": "upload refused"}
        finished = datetime.now().isoformat(timespec="seconds")
        with get_connection() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO maintenance_flags (flag, executed_at) VALUES (?, ?)",
                (BACKUP_FLAG, finished),
            )
        return {"ok": True, "at": finished, "bytes": size, "key": f"{BACKUP_PREFIX}/{stamp}.db.gz"}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:200]}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
