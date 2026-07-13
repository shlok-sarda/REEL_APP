import os
import signal
import subprocess
import sys
import traceback
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import settings
from app.db.database import get_connection
from app.db.init_db import initialize_database
from app.services.jobs import claim_next_job, complete_job, create_worker_lock, fail_job, release_worker_lock
from app.services.reel_ingest import get_reel_by_id


def failure_summary_for_reel(reel_id: str) -> str:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT summary
            FROM reel_items
            WHERE reel_id = ? AND item_name = 'Processing Failed'
            ORDER BY id DESC
            LIMIT 1
            """,
            (reel_id,),
        ).fetchone()
    if row and row["summary"]:
        return row["summary"]
    return "Reel processor returned failed output"


def run_processor(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run the processor in its own process group so a timeout kills the whole
    tree. A plain subprocess.run timeout only kills the direct child, leaving
    yt-dlp/ffmpeg grandchildren (spawned without their own timeout) running."""
    process = subprocess.Popen(
        cmd,
        cwd=str(settings.processor_script.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=settings.processor_timeout_seconds)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()
        try:
            process.communicate(timeout=30)
        except Exception:
            pass
        raise
    return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)


def process_job(job: dict):
    claim_token = job.get("started_at") or None
    try:
        cmd = [
            sys.executable,
            str(settings.processor_script),
            "--user-id",
            job["user_id"],
        ]
        if job["job_type"] != "rebuild_library":
            reel = get_reel_by_id(job["reel_id"])
            if not reel:
                fail_job(job["id"], "Missing reel for job", claim_token)
                return
            cmd += ["--only-url", reel["url"]]
        result = run_processor(cmd)
    except subprocess.TimeoutExpired:
        fail_job(job["id"], f"Processor timed out after {settings.processor_timeout_seconds}s", claim_token)
        return
    except Exception as exc:
        detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        fail_job(job["id"], f"Worker error: {detail}", claim_token)
        return

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Processor failed"
        fail_job(job["id"], message, claim_token)
        return

    if job["job_type"] == "process_reel":
        reel = get_reel_by_id(job["reel_id"])
        if not reel:
            fail_job(job["id"], "Missing reel after processing", claim_token)
            return
        if reel.get("status") != "completed":
            fail_job(job["id"], failure_summary_for_reel(job["reel_id"]), claim_token)
            return

    try:
        # Lazy import: keeps the resident worker lean; the deep-search stack
        # (openai/meilisearch clients) only loads for this post-processing step.
        from app.services.deep_search import index_user_documents, rebuild_deep_search_documents

        if settings.meili_host:
            index_user_documents(job["user_id"])
        else:
            rebuild_deep_search_documents(job["user_id"])
    except Exception:
        pass

    # Auto-route the freshly-processed reel into the user's smart folders.
    # Wrapped so a routing failure can NEVER fail reel processing. No-op for
    # users with no folders (the loop just doesn't run).
    if job["job_type"] == "process_reel":
        try:
            from app.services.folders import route_reel

            route_reel(job["user_id"], job["reel_id"])
        except Exception:
            pass

    complete_job(job["id"], claim_token)


def main():
    """Process one job, then re-exec into a fresh process for the next.

    The container has 512MB total for uvicorn + this worker + the processor
    subprocess. Handling one job per process image means any memory the job
    leaves behind (client caches, allocator fragmentation) is returned to the
    OS before the next claim, instead of accumulating across a long backlog
    until the instance OOMs. The re-exec keeps the same PID, so the worker
    lock stays valid across the chain (create_worker_lock adopts its own PID).
    """
    initialize_database()
    if not create_worker_lock():
        return

    job = None
    try:
        job = claim_next_job()
        if job:
            process_job(job)
    except BaseException:
        release_worker_lock()
        raise

    if not job:
        release_worker_lock()
        return

    try:
        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())])
    except OSError:
        release_worker_lock()


if __name__ == "__main__":
    main()
