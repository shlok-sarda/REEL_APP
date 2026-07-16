import secrets as _secrets

from fastapi import APIRouter, HTTPException, status

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


def _queue_debug(full: bool = False) -> dict:
    """Read-only view of the recovery machinery's inputs, for remote triage.

    The default (public) view carries only operational vitals safe for an
    unauthenticated endpoint. full=True adds worker/job forensics — including
    other users' reel ids and error text — so it requires the debug token.
    """
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
    if not full:
        return info
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
            reel_columns = [
                row["name"] for row in connection.execute("PRAGMA table_info(reels)").fetchall()
            ]
        info["running_started_at"] = [f"{row['job_type']}:{row['started_at']}" for row in rows]
        info["reels_columns"] = reel_columns
        with get_connection() as connection:
            failure_rows = connection.execute(
                """
                SELECT reel_id, error_message, finished_at
                FROM processing_jobs
                WHERE status = 'failed'
                ORDER BY id DESC
                LIMIT 8
                """
            ).fetchall()
        info["recent_failures"] = [
            f"{row['finished_at']} {row['reel_id']}: {row['error_message'] or ''}"
            for row in failure_rows
        ]
    except Exception as exc:
        info["error"] = str(exc)[:200]
    return info


def _run_inline_fix() -> dict:
    """Run queue recovery in-request and report exactly what happened.

    Remote triage tool: the janitor's failures are only visible in server
    logs, so this exposes each stage's rowcount/exception in the response.
    Everything here is idempotent maintenance the janitor already attempts.
    """
    import subprocess
    import sys
    import time
    from datetime import datetime, timedelta

    report: dict = {}
    from app.db.database import get_connection

    try:
        from app.services.jobs import is_worker_running

        report["worker_alive"] = is_worker_running()
    except Exception as exc:
        report["worker_alive_error"] = repr(exc)[:300]
    # Stage 1: the real service-path recovery, with its error surfaced.
    try:
        from app.services.jobs import recover_orphaned_jobs

        report["service_recovered"] = recover_orphaned_jobs()
    except Exception as exc:
        report["service_recover_error"] = repr(exc)[:300]
    # Stage 2: raw fallback requeue — stale claims only, so a live worker's
    # in-flight job is never yanked into double processing.
    try:
        stale_cutoff = (datetime.now() - timedelta(seconds=1500)).isoformat(timespec="seconds")
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE processing_jobs
                SET status = 'pending', started_at = ''
                WHERE status = 'running'
                  AND started_at < ?
                """,
                (stale_cutoff,),
            )
            report["raw_requeued_stale"] = cursor.rowcount
    except Exception as exc:
        report["raw_requeue_error"] = repr(exc)[:300]
    # Stage 3: run the real worker synchronously with output captured. If it
    # crashes before creating its lock we finally see the traceback; if it's
    # healthy we see it claim a job (the 25s kill orphans that claim, which
    # stale recovery requeues — acceptable for a manual diagnostic).
    try:
        repo_root = settings.worker_script.parent.parent.parent
        try:
            probe = subprocess.run(
                [sys.executable, str(settings.worker_script)],
                capture_output=True,
                text=True,
                timeout=25,
                cwd=str(repo_root),
            )
            output = (probe.stdout or "") + "\n" + (probe.stderr or "")
            report["worker_run"] = f"exit={probe.returncode} {output[-600:].strip()}"
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or b"", exc.stderr or b"")
            text_out = " ".join(
                part.decode("utf-8", "replace") if isinstance(part, bytes) else part for part in out
            )
            report["worker_run"] = f"still_running_at_25s {text_out[-600:].strip()}"
    except Exception as exc:
        report["worker_run_error"] = repr(exc)[:300]
    # Stage 3.5: is the OpenAI key alive and funded? A dead key/quota makes
    # every reel fail at the first step that calls the API. One 1-token
    # embedding per manual fix=1 invocation — negligible cost.
    try:
        import os as _os

        from openai import OpenAI

        _key = _os.getenv("OPENAI_API_KEY", "").strip()
        if not _key:
            report["openai_probe"] = "NO KEY IN ENV"
        else:
            _client = OpenAI(api_key=_key, timeout=20, max_retries=0)
            _client.embeddings.create(model="text-embedding-3-small", input="ping")
            report["openai_probe"] = "ok — paid call accepted"
    except Exception as exc:
        report["openai_probe"] = f"FAILED: {exc}"[:300]
    # Stage 4: kick the janitor, give a spawned worker a moment, then inspect.
    try:
        from app.services.jobs import ensure_background_progress

        ensure_background_progress()
        report["ensure_background_progress"] = "ok"
    except Exception as exc:
        report["ensure_error"] = repr(exc)[:300]
    time.sleep(3)
    try:
        report["lock_after"] = settings.worker_lock_file.exists()
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS n FROM processing_jobs GROUP BY status"
            ).fetchall()
        report["queue_after"] = {row["status"]: row["n"] for row in rows}
    except Exception as exc:
        report["queue_after_error"] = repr(exc)[:300]
    return report


def _debug_authorized(token: str) -> bool:
    # Reuses the ingest secret so no new env var is needed. Fails closed when
    # the secret is unset — the full debug view stays off rather than open.
    secret = settings.telegram_ingest_secret
    return bool(secret) and _secrets.compare_digest(token.strip(), secret)


@router.get("/health", response_model=HealthResponse)
def health_check(fix: int = 0, token: str = ""):
    ensure_storage()
    authorized = _debug_authorized(token)
    if fix and not authorized:
        # fix=1 runs heavy recovery (25s synchronous worker probe, a paid
        # OpenAI call) — not something the open internet gets to trigger.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Debug token required")
    debug = _queue_debug(full=authorized)
    if fix:
        debug["fix_report"] = _run_inline_fix()
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
        queue_debug=debug,
    )
