from fastapi import APIRouter

from app.config import settings
from app.schemas import HealthResponse
from app.services.reel_ingest import ensure_storage


router = APIRouter(tags=["health"])


def _queue_snapshot() -> dict:
    # Raw counts only — deliberately no janitor/recovery side effects here,
    # since health checks may be polled frequently.
    try:
        from app.db.database import get_connection

        with get_connection() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS n FROM processing_jobs GROUP BY status"
            ).fetchall()
        return {row["status"]: row["n"] for row in rows}
    except Exception:
        return {}


def _queue_debug() -> dict:
    """Read-only view of the recovery machinery's inputs, for remote triage."""
    import os
    import time
    from datetime import datetime

    info: dict = {
        "git_commit": os.getenv("RENDER_GIT_COMMIT", "")[:10],
        "server_now": datetime.now().isoformat(timespec="seconds"),
        "processor_timeout_seconds": settings.processor_timeout_seconds,
    }
    try:
        import shutil

        usage = shutil.disk_usage(settings.storage_dir)
        info["disk"] = {
            "total_mb": usage.total // (1024 * 1024),
            "free_mb": usage.free // (1024 * 1024),
        }
        # Distinguish "disk full" from other write failures directly.
        from app.db.database import get_connection

        with get_connection() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS write_probe (id INTEGER PRIMARY KEY, ts TEXT)"
            )
            connection.execute("DELETE FROM write_probe")
            connection.execute("INSERT INTO write_probe (ts) VALUES (?)", (info["server_now"],))
        info["db_writable"] = True
    except Exception as exc:
        info["db_writable"] = False
        info["db_write_error"] = str(exc)[:200]
    try:
        from app.services.jobs import _pid_is_worker, _stale_cutoff_for

        info["stale_cutoff_process_reel"] = _stale_cutoff_for("process_reel")
        lock = settings.worker_lock_file
        if lock.exists():
            entry: dict = {"exists": True}
            try:
                entry["age_seconds"] = int(time.time() - lock.stat().st_mtime)
                pid = int(lock.read_text().strip())
                entry["pid"] = pid
                entry["pid_is_worker"] = _pid_is_worker(pid)
            except Exception as exc:
                entry["error"] = str(exc)[:120]
            info["worker_lock"] = entry
        else:
            info["worker_lock"] = {"exists": False}
        from app.db.database import get_connection

        with get_connection() as connection:
            rows = connection.execute(
                "SELECT job_type, started_at FROM processing_jobs WHERE status = 'running' ORDER BY id DESC LIMIT 25"
            ).fetchall()
        info["running_started_at"] = [f"{row['job_type']}:{row['started_at']}" for row in rows]
    except Exception as exc:
        info["error"] = str(exc)[:200]
    return info


@router.get("/health", response_model=HealthResponse)
def health_check():
    ensure_storage()
    return HealthResponse(
        service="reel-organizer-api",
        endpoint="/instagram/webhook",
        environment=settings.app_env,
        storage_dir=str(settings.storage_dir),
        media_dir=str(settings.media_dir),
        csv_file=str(settings.reel_urls_csv),
        media_storage_mode="r2+local_cache" if settings.r2_enabled else "local_only",
        r2_enabled=settings.r2_enabled,
        queue=_queue_snapshot(),
        queue_debug=_queue_debug(),
    )
