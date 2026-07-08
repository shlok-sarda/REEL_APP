import os
import subprocess
import sys
from datetime import datetime

from app.config import settings
from app.db.database import get_connection

MAX_PROCESS_REEL_ATTEMPTS = 2
MAX_REBUILD_ATTEMPTS = 2


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def enqueue_reel_job(reel_id: str, user_id: str = "default", job_type: str = "process_reel") -> dict:
    with get_connection() as connection:
        existing = connection.execute(
            """
            SELECT id, reel_id, user_id, job_type, status, attempts, error_message, created_at, started_at, finished_at
            FROM processing_jobs
            WHERE reel_id = ? AND job_type = ? AND status IN ('pending', 'running')
            ORDER BY id DESC
            LIMIT 1
            """,
            (reel_id, job_type),
        ).fetchone()
        if existing:
            return dict(existing)

        connection.execute(
            """
            INSERT INTO processing_jobs (
                reel_id, user_id, job_type, status, attempts, error_message, created_at, started_at, finished_at
            )
            VALUES (?, ?, ?, 'pending', 0, '', ?, '', '')
            """,
            (reel_id, user_id, job_type, _now()),
        )
        row = connection.execute(
            """
            SELECT id, reel_id, user_id, job_type, status, attempts, error_message, created_at, started_at, finished_at
            FROM processing_jobs
            WHERE reel_id = ? AND job_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (reel_id, job_type),
        ).fetchone()
    return dict(row)


def enqueue_library_rebuild_job(user_id: str = "default") -> dict:
    return enqueue_reel_job(f"library:{user_id}", user_id=user_id, job_type="rebuild_library")


def list_jobs(limit: int = 100, user_id: str | None = None) -> list[dict]:
    ensure_background_progress(user_id=user_id)
    query = """
        SELECT
            processing_jobs.id,
            processing_jobs.reel_id,
            processing_jobs.user_id,
            processing_jobs.job_type,
            processing_jobs.status,
            processing_jobs.attempts,
            processing_jobs.error_message,
            processing_jobs.created_at,
            processing_jobs.started_at,
            processing_jobs.finished_at,
            COALESCE(reels.url, '') AS reel_url,
            COALESCE(reels.shortcode, '') AS reel_shortcode
        FROM processing_jobs
        LEFT JOIN reels ON reels.id = processing_jobs.reel_id
    """
    params = []
    if user_id:
        query += " WHERE processing_jobs.user_id = ?"
        params.append(user_id)
    query += " ORDER BY processing_jobs.id DESC LIMIT ?"
    params.append(limit)
    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def job_counts(user_id: str | None = None) -> dict:
    ensure_background_progress(user_id=user_id)
    query = """
        SELECT status, COUNT(*) AS count
        FROM processing_jobs
    """
    params = []
    if user_id:
        query += " WHERE user_id = ?"
        params.append(user_id)
    query += " GROUP BY status"
    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
    counts = {row["status"]: row["count"] for row in rows}
    return {
        "pending": counts.get("pending", 0),
        "running": counts.get("running", 0),
        "failed": counts.get("failed", 0),
        "completed": counts.get("completed", 0),
    }


def claim_next_job() -> dict | None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE processing_jobs
            SET status = 'failed',
                error_message = CASE
                    WHEN error_message = '' THEN 'Reel processing interrupted repeatedly'
                    ELSE error_message
                END,
                finished_at = ?
            WHERE status = 'pending'
              AND job_type = 'process_reel'
              AND attempts >= ?
            """,
            (_now(), MAX_PROCESS_REEL_ATTEMPTS),
        )
        connection.execute(
            """
            UPDATE processing_jobs
            SET status = 'failed',
                error_message = CASE
                    WHEN error_message = '' THEN 'Library rebuild interrupted repeatedly'
                    ELSE error_message
                END,
                finished_at = ?
            WHERE status = 'pending'
              AND job_type = 'rebuild_library'
              AND attempts >= ?
            """,
            (_now(), MAX_REBUILD_ATTEMPTS),
        )
        row = connection.execute(
            """
            SELECT id, reel_id, user_id, job_type, status, attempts, error_message, created_at, started_at, finished_at
            FROM processing_jobs
            WHERE status = 'pending'
            ORDER BY
                CASE
                    WHEN job_type = 'process_reel' THEN 0
                    WHEN job_type = 'rebuild_library' THEN 1
                    ELSE 2
                END ASC,
                id ASC
            LIMIT 1
            """,
        ).fetchone()
        if not row:
            return None
        job = dict(row)
        connection.execute(
            """
            UPDATE processing_jobs
            SET status = 'running', attempts = attempts + 1, started_at = ?, error_message = ''
            WHERE id = ?
            """,
            (_now(), job["id"]),
        )
        updated = connection.execute(
            """
            SELECT id, reel_id, user_id, job_type, status, attempts, error_message, created_at, started_at, finished_at
            FROM processing_jobs
            WHERE id = ?
            """,
            (job["id"],),
        ).fetchone()
    return dict(updated)


def complete_job(job_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE processing_jobs
            SET status = 'completed', finished_at = ?
            WHERE id = ?
            """,
            (_now(), job_id),
        )


def fail_job(job_id: int, error_message: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE processing_jobs
            SET status = 'failed', error_message = ?, finished_at = ?
            WHERE id = ?
            """,
            ((error_message or "")[:500], _now(), job_id),
        )


def is_worker_running() -> bool:
    if not settings.worker_lock_file.exists():
        return False
    try:
        pid = int(settings.worker_lock_file.read_text().strip())
    except Exception:
        settings.worker_lock_file.unlink(missing_ok=True)
        return False

    try:
        os.kill(pid, 0)
        return True
    except OSError:
        settings.worker_lock_file.unlink(missing_ok=True)
        return False


def start_worker_if_needed() -> bool:
    if is_worker_running():
        return False

    subprocess.Popen(
        [sys.executable, str(settings.worker_script)],
        cwd=str(settings.worker_script.parent.parent.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def recover_orphaned_jobs() -> int:
    if is_worker_running():
        return 0
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE processing_jobs
            SET status = 'failed',
                error_message = CASE
                    WHEN error_message = '' THEN 'Reel processing interrupted repeatedly'
                    ELSE error_message
                END,
                finished_at = ?
            WHERE status = 'running'
              AND job_type = 'process_reel'
              AND attempts >= ?
            """,
            (_now(), MAX_PROCESS_REEL_ATTEMPTS),
        )
        connection.execute(
            """
            UPDATE processing_jobs
            SET status = 'failed',
                error_message = CASE
                    WHEN error_message = '' THEN 'Library rebuild interrupted repeatedly'
                    ELSE error_message
                END,
                finished_at = ?
            WHERE status = 'running'
              AND job_type = 'rebuild_library'
              AND attempts >= ?
            """,
            (_now(), MAX_REBUILD_ATTEMPTS),
        )
        cursor = connection.execute(
            """
            UPDATE processing_jobs
            SET status = 'pending', error_message = CASE
                WHEN error_message = '' THEN 'Recovered after worker interruption'
                ELSE error_message
            END
            WHERE status = 'running'
              AND NOT (job_type = 'process_reel' AND attempts >= ?)
              AND NOT (job_type = 'rebuild_library' AND attempts >= ?)
            """
            ,
            (MAX_PROCESS_REEL_ATTEMPTS, MAX_REBUILD_ATTEMPTS),
        )
        recovered = cursor.rowcount
        reconciled = reconcile_stuck_reels(connection)
    if reconciled:
        # Keep the CSV mirror in sync when reels leave the non-terminal state.
        # Lazy import avoids a circular dependency with reel_ingest.
        try:
            from app.services.reel_ingest import sync_csv_from_db

            sync_csv_from_db()
        except Exception:
            pass
    return recovered


def reconcile_stuck_reels(connection) -> int:
    """Flip reels that are stranded in a non-terminal status to 'failed'.

    A reel is set to 'processing' before its processor subprocess runs. If that
    subprocess dies mid-run (timeout, container restart/redeploy, OOM) the code
    that writes the reel's final status never executes, so the reel is left in
    'processing'/'pending' forever while its job is already 'failed'. The
    dashboard counts any reel that is not 'completed'/'failed' as "waiting",
    which is the "always N reels waiting" bug. Here we reconcile only reels that
    have a failed process_reel job and no still-active (pending/running) job, so
    freshly-ingested reels awaiting their first run are never touched.

    Must be called with the worker known to be idle (see recover_orphaned_jobs),
    so a reel legitimately being processed right now is never marked failed.
    """
    cursor = connection.execute(
        """
        UPDATE reels
        SET status = 'failed', updated_at = ?
        WHERE status IN ('pending', 'processing')
          AND EXISTS (
              SELECT 1 FROM processing_jobs j
              WHERE j.reel_id = reels.id
                AND j.job_type = 'process_reel'
                AND j.status = 'failed'
          )
          AND NOT EXISTS (
              SELECT 1 FROM processing_jobs j2
              WHERE j2.reel_id = reels.id
                AND j2.job_type = 'process_reel'
                AND j2.status IN ('pending', 'running')
          )
        """,
        (_now(),),
    )
    return cursor.rowcount


def ensure_background_progress(user_id: str | None = None) -> None:
    recover_orphaned_jobs()
    if is_worker_running():
        return
    query = "SELECT COUNT(*) FROM processing_jobs WHERE status = 'pending'"
    params = []
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    with get_connection() as connection:
        pending = connection.execute(query, params).fetchone()[0]
    if pending:
        start_worker_if_needed()


def create_worker_lock() -> bool:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(settings.worker_lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
        return True
    except FileExistsError:
        return False


def release_worker_lock() -> None:
    settings.worker_lock_file.unlink(missing_ok=True)
