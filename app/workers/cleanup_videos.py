"""Free the persistent disk: delete local videos that already live in R2.

Media downloads are cached on the persistent disk and were never deleted
after their R2 upload, so reprocessing sprees fill the 1GB disk — at which
point every SQLite write fails ("database or disk is full"), the worker
can't even write its lock file, and the whole queue freezes while reads
keep working. Playback doesn't need the local copies: the media URL builder
falls back to a presigned R2 URL whenever the local file is missing.

Deliberately does zero DB writes so it works on a full disk. Files newer
than one hour are skipped so an in-flight job's media is never yanked.
"""
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import settings

MIN_AGE_SECONDS = 3600


def main() -> None:
    from app.services.object_storage import object_exists, r2_is_enabled

    if not r2_is_enabled():
        print("[cleanup] R2 disabled; refusing to delete local-only media", flush=True)
        return

    videos_dir = settings.videos_dir
    if not videos_dir.exists():
        return

    now = time.time()
    freed = 0
    kept = 0
    deleted = 0
    for path in sorted(videos_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            if now - path.stat().st_mtime < MIN_AGE_SECONDS:
                kept += 1
                continue
            size = path.stat().st_size
            if object_exists(f"videos/{path.name}"):
                path.unlink()
                freed += size
                deleted += 1
            else:
                kept += 1
        except Exception as exc:
            print(f"[cleanup] {path.name}: {exc}", flush=True)
    print(
        f"[cleanup] deleted {deleted} R2-backed videos ({freed // (1024 * 1024)}MB freed), kept {kept}",
        flush=True,
    )


if __name__ == "__main__":
    main()
