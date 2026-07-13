"""One-shot thumbnail repair for reels whose local media was lost.

Deploys rebuild the container filesystem; any thumbnail that lived only in
media_dir (not uploaded to R2, or with an empty thumbnail_path in the DB)
disappears from the app even though the reel is fine. This walks completed
reels and, for each missing thumbnail, restores it in cost order:

1. re-download the thumbnail from R2;
2. else regenerate it from a local or R2 copy of the video;
3. else (capped) re-download the reel via the normal media path (Apify).

Runs as its own process so the cv2/boto3 memory cost never lands in the web
app or queue worker. Guarded by a maintenance flag that is only written after
a *complete* pass, so an interrupted run resumes on the next janitor tick.
"""
import os
import sys
import time
from datetime import datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import settings
from app.db.database import get_connection
from app.db.init_db import initialize_database

REPAIR_FLAG = "repair_media_v1"
MAX_FULL_REDOWNLOADS = 20
MAX_RUNTIME_SECONDS = 20 * 60
VIDEO_SUFFIXES = (".mp4", ".webm", ".mov", ".mkv")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def repair_flag_done() -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM maintenance_flags WHERE flag = ? LIMIT 1", (REPAIR_FLAG,)
        ).fetchone()
    return bool(row)


def _mark_done() -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO maintenance_flags (flag, executed_at) VALUES (?, ?)",
            (REPAIR_FLAG, _now()),
        )


def _lock_path() -> Path:
    return settings.storage_dir / "media_repair.lock"


def acquire_lock() -> bool:
    lock = _lock_path()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    if lock.exists():
        try:
            pid = int(lock.read_text().strip())
            os.kill(pid, 0)
            return False  # a repair process is already running
        except Exception:
            lock.unlink(missing_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
        return True
    except FileExistsError:
        return False


def _set_thumbnail_path(reel_id: str, thumbnail_path: str) -> None:
    with get_connection() as connection:
        connection.execute(
            "UPDATE reels SET thumbnail_path = ?, updated_at = ? WHERE id = ?",
            (thumbnail_path, _now(), reel_id),
        )


def _local_file(path_value: str) -> Path | None:
    value = (path_value or "").strip()
    if not value or value.startswith(("http://", "https://")):
        return None
    path = Path(value)
    return path if path.exists() and path.is_file() else None


def _find_local_video(reel: dict) -> Path | None:
    existing = _local_file(reel.get("local_video_path", ""))
    if existing:
        return existing
    for suffix in VIDEO_SUFFIXES:
        candidate = settings.videos_dir / f"{reel['id']}{suffix}"
        if candidate.exists():
            return candidate
    return None


def repair_reel(reel: dict, redownload_budget: int) -> tuple[str, int]:
    """Return (outcome, redownloads_used)."""
    from app.services.object_storage import download_file, object_exists, r2_is_enabled, upload_file

    reel_id = reel["id"]
    thumb_local = settings.thumbnails_dir / f"{reel_id}.jpg"
    thumb_key = f"thumbnails/{reel_id}.jpg"

    existing_thumb = _local_file(reel.get("thumbnail_path", "")) or (
        thumb_local if thumb_local.exists() else None
    )
    if existing_thumb:
        if not (reel.get("thumbnail_path") or "").strip():
            _set_thumbnail_path(reel_id, str(existing_thumb))
        # Deploy-proof it: make sure R2 has a copy for the presign fallback.
        if r2_is_enabled() and not object_exists(thumb_key):
            try:
                upload_file(existing_thumb, thumb_key, content_type="image/jpeg")
            except Exception:
                pass
        return "ok", 0

    if r2_is_enabled() and object_exists(thumb_key):
        if download_file(thumb_key, thumb_local):
            _set_thumbnail_path(reel_id, str(thumb_local))
            return "restored_from_r2", 0

    video = _find_local_video(reel)
    if video is None and r2_is_enabled():
        for suffix in VIDEO_SUFFIXES:
            video_key = f"videos/{reel_id}{suffix}"
            if object_exists(video_key):
                candidate = settings.videos_dir / f"{reel_id}{suffix}"
                if download_file(video_key, candidate):
                    video = candidate
                break

    if video is not None:
        from app.services.media import _make_thumbnail, _upload_media_to_r2

        thumbnail = _make_thumbnail(video, reel_id)
        if thumbnail:
            _set_thumbnail_path(reel_id, str(thumbnail))
            try:
                _upload_media_to_r2(video, thumbnail)
            except Exception:
                pass
            return "regenerated_from_video", 0
        return "video_unreadable", 0

    if redownload_budget > 0:
        from app.services.media import ensure_reel_media

        try:
            result = ensure_reel_media(reel["url"])
        except Exception as exc:
            print(f"[repair] full redownload failed for {reel_id}: {exc}", flush=True)
            return "redownload_failed", 1
        if result.get("thumbnail_path"):
            return "redownloaded", 1
        return "redownload_failed", 1

    return "skipped_no_budget", 0


def main() -> None:
    initialize_database()
    if repair_flag_done():
        return
    if not acquire_lock():
        return

    started = time.time()
    counts: dict[str, int] = {}
    redownloads = 0
    completed_pass = True
    try:
        with get_connection() as connection:
            reels = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT id, user_id, url, local_video_path, thumbnail_path
                    FROM reels
                    WHERE status = 'completed'
                    ORDER BY received_at DESC
                    """
                ).fetchall()
            ]
        for reel in reels:
            if time.time() - started > MAX_RUNTIME_SECONDS:
                completed_pass = False
                break
            try:
                outcome, used = repair_reel(reel, MAX_FULL_REDOWNLOADS - redownloads)
            except Exception as exc:
                outcome, used = "error", 0
                print(f"[repair] {reel['id']}: {exc}", flush=True)
            redownloads += used
            counts[outcome] = counts.get(outcome, 0) + 1
        if completed_pass:
            _mark_done()
        print(
            f"[repair] pass {'complete' if completed_pass else 'partial (resumes next tick)'}: "
            f"{counts} over {len(reels)} completed reels",
            flush=True,
        )
    finally:
        _lock_path().unlink(missing_ok=True)


if __name__ == "__main__":
    main()
