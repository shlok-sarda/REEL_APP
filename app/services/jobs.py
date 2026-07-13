import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from app.config import settings
from app.db.database import get_connection

MAX_PROCESS_REEL_ATTEMPTS = 3
MAX_REBUILD_ATTEMPTS = 2

# Slack on top of the hard processor timeout before a 'running' job is treated
# as dead regardless of what the worker lock file claims.
STALE_RUNNING_GRACE_SECONDS = 600


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _stale_running_cutoff() -> str:
    grace = settings.processor_timeout_seconds + STALE_RUNNING_GRACE_SECONDS
    return (datetime.now() - timedelta(seconds=grace)).isoformat(timespec="seconds")


def _fail_exhausted_jobs(connection, status: str, stale_cutoff: str | None = None) -> None:
    """Flip jobs of the given status that are out of attempts to 'failed'."""
    for job_type, max_attempts, label in (
        ("process_reel", MAX_PROCESS_REEL_ATTEMPTS, "Reel processing interrupted repeatedly"),
        ("rebuild_library", MAX_REBUILD_ATTEMPTS, "Library rebuild interrupted repeatedly"),
    ):
        query = """
            UPDATE processing_jobs
            SET status = 'failed',
                error_message = CASE
                    WHEN error_message = '' THEN ?
                    ELSE error_message
                END,
                finished_at = ?
            WHERE status = ?
              AND job_type = ?
              AND attempts >= ?
        """
        params: list = [label, _now(), status, job_type, max_attempts]
        if stale_cutoff is not None:
            query += " AND started_at < ?"
            params.append(stale_cutoff)
        connection.execute(query, params)


def recover_stale_running_jobs(connection) -> int:
    """Requeue 'running' jobs whose subprocess must be long dead.

    Every job run is hard-capped at processor_timeout_seconds, so a job still
    marked 'running' well past that cutoff is an orphan — its worker was killed
    mid-job (deploy/restart/OOM) or a stale lock file is blocking the normal
    recovery path. This check is purely time-based and deliberately ignores the
    worker lock: the one live worker can only ever hold a claim younger than
    the cutoff, so requeueing older claims can never touch an in-flight job.
    """
    cutoff = _stale_running_cutoff()
    _fail_exhausted_jobs(connection, "running", stale_cutoff=cutoff)
    cursor = connection.execute(
        """
        UPDATE processing_jobs
        SET status = 'pending',
            started_at = '',
            error_message = CASE
                WHEN error_message = '' THEN 'Recovered after stalled run'
                ELSE error_message
            END
        WHERE status = 'running'
          AND started_at < ?
        """,
        (cutoff,),
    )
    return cursor.rowcount


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
        # Self-heal before claiming: requeue orphaned 'running' rows left behind
        # by a worker that died mid-job, then retire jobs that are out of attempts.
        recover_stale_running_jobs(connection)
        _fail_exhausted_jobs(connection, "pending")
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


def complete_job(job_id: int, claim_started_at: str | None = None) -> None:
    query = """
        UPDATE processing_jobs
        SET status = 'completed', finished_at = ?
        WHERE id = ?
    """
    params: list = [_now(), job_id]
    if claim_started_at:
        # Only finalize our own claim: if the job was requeued and re-claimed
        # after this worker stalled, leave the newer claim alone.
        query += " AND status = 'running' AND started_at = ?"
        params.append(claim_started_at)
    with get_connection() as connection:
        connection.execute(query, params)


def fail_job(job_id: int, error_message: str, claim_started_at: str | None = None) -> None:
    query = """
        UPDATE processing_jobs
        SET status = 'failed', error_message = ?, finished_at = ?
        WHERE id = ?
    """
    params: list = [(error_message or "")[:500], _now(), job_id]
    if claim_started_at:
        query += " AND status = 'running' AND started_at = ?"
        params.append(claim_started_at)
    with get_connection() as connection:
        connection.execute(query, params)


def _pid_is_worker(pid: int) -> bool:
    """Check the process is actually our queue worker, not a reused PID.

    After a container restart the lock file survives (storage dir is on the
    persistent disk) while its PID gets recycled by unrelated processes, which
    made the old bare os.kill(pid, 0) check report a phantom worker forever —
    blocking both orphan recovery and new worker startup.
    """
    try:
        os.kill(pid, 0)
    except OSError:
        # No such process — or owned by another user, which our worker never is.
        return False

    proc_cmdline = Path(f"/proc/{pid}/cmdline")
    if Path("/proc").is_dir():  # Linux (Render)
        try:
            cmdline = proc_cmdline.read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        except OSError:
            return False
        return "process_queue" in cmdline

    try:  # macOS (local dev)
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        # Can't verify: assume alive so we never spawn a duplicate worker.
        # Stale-time recovery still unfreezes jobs even if this is wrong.
        return True
    if result.returncode != 0:
        return False
    return "process_queue" in result.stdout


def is_worker_running() -> bool:
    lock_file = settings.worker_lock_file
    if not lock_file.exists():
        return False
    try:
        pid = int(lock_file.read_text().strip())
    except Exception:
        # Unreadable or empty. A worker that just created the lock may not have
        # written its PID yet, so give a fresh file a grace window instead of
        # deleting a live worker's lock out from under it.
        try:
            is_fresh = (time.time() - lock_file.stat().st_mtime) < 30
        except OSError:
            return False
        if is_fresh:
            return True
        lock_file.unlink(missing_ok=True)
        return False

    if _pid_is_worker(pid):
        return True
    lock_file.unlink(missing_ok=True)
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
    worker_alive = is_worker_running()
    with get_connection() as connection:
        # Always requeue jobs stuck 'running' past the hard timeout — this is
        # safe even with a live worker (its current claim is always fresh) and
        # is what unfreezes the queue when the lock check is wrong.
        recovered = recover_stale_running_jobs(connection)
        if not worker_alive:
            _fail_exhausted_jobs(connection, "running")
            cursor = connection.execute(
                """
                UPDATE processing_jobs
                SET status = 'pending',
                    started_at = '',
                    error_message = CASE
                        WHEN error_message = '' THEN 'Recovered after worker interruption'
                        ELSE error_message
                    END
                WHERE status = 'running'
                """
            )
            recovered += cursor.rowcount
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
    freshly-ingested reels awaiting their first run — and reels a live worker is
    processing right now (their job is 'running') — are never touched.
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


JOB_BACKFILL_LIMIT = 25


def enqueue_missing_reel_jobs(limit: int = JOB_BACKFILL_LIMIT) -> int:
    """Re-enqueue reels stranded in a non-terminal status with no job at all.

    Job rows and reel rows can fall out of sync (a purge/reset that kept the
    reel, a partial ingest, a cleared jobs table): the reel then sits 'pending'
    forever while the queue is empty and the worker has nothing to claim.
    Recreate one process_reel job per such reel so the pipeline converges.
    Reels whose jobs still exist — including failed ones — are never touched.
    """
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, user_id
            FROM reels
            WHERE status IN ('pending', 'processing')
              AND NOT EXISTS (
                  SELECT 1 FROM processing_jobs j
                  WHERE j.reel_id = reels.id
                    AND j.job_type = 'process_reel'
              )
            ORDER BY received_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    created = 0
    for row in rows:
        try:
            enqueue_reel_job(row["id"], user_id=row["user_id"])
            created += 1
        except Exception as exc:
            print(f"[jobs] backfill enqueue failed for {row['id']}: {exc}", flush=True)
    return created


def ensure_background_progress(user_id: str | None = None) -> None:
    # Janitor duties: recover orphans, backfill missing jobs, start the worker.
    # Each step is isolated — this runs inside /jobs and /dashboard requests,
    # so a broken janitor must degrade to a log line, never a 500.
    try:
        recover_orphaned_jobs()
    except Exception as exc:
        print(f"[jobs] orphan recovery failed: {exc}", flush=True)
    try:
        enqueue_missing_reel_jobs()
    except Exception as exc:
        print(f"[jobs] missing-job backfill failed: {exc}", flush=True)
    try:
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
    except Exception as exc:
        print(f"[jobs] worker start failed: {exc}", flush=True)


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
