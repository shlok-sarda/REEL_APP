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
from app.services.jobs import (
    claim_next_job,
    complete_job,
    create_worker_lock,
    fail_job,
    is_quota_failure,
    job_timeout_seconds,
    pause_queue_for_quota,
    release_worker_lock,
)
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


def run_processor(cmd: list[str], timeout_seconds: int) -> subprocess.CompletedProcess:
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
        stdout, stderr = process.communicate(timeout=timeout_seconds)
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


def rebuild_shelves_for(user_id: str) -> None:
    """Route Collections shelves. Never raises — shelves are never worth a job.

    Only for accounts that actually DISPLAY router shelves: routing costs three
    LLM calls per new reel, so running it more widely bills for shelves nobody
    ever looks at, and that waste scales with the user base rather than with
    the allowlist.
    """
    try:
        from app.services.collections import rebuild_user_shelves
        from app.services.library import router_shelves_enabled

        if not router_shelves_enabled(user_id):
            return
        summary = rebuild_user_shelves(user_id)
        print(f"[collections] {user_id}: {summary['shelved']} reels on "
              f"{len(summary['published_shelves'])} shelves, {summary['llm_calls']} llm calls")
    except Exception as exc:
        print(f"[collections] shelf rebuild skipped for {user_id}: {exc}")


def reel_is_finished(job: dict) -> bool:
    """True when this job's reel was fully read, whatever the processor's exit
    says: the row is completed and it has a real (non-failure) item."""
    if job.get("job_type") != "process_reel":
        return False
    try:
        reel = get_reel_by_id(job["reel_id"])
        if not reel or reel.get("status") != "completed":
            return False
        with get_connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM reel_items WHERE reel_id = ? AND item_name != 'Processing Failed' LIMIT 1",
                (job["reel_id"],),
            ).fetchone()
        return bool(row)
    except Exception:
        return False


def fail_reel_job(job: dict, message: str, claim_token: str | None) -> None:
    """Fail the job and tell the owner. A failed job is final (nothing retries
    it), and the owner was already told their reel is processing, so without
    this they wait on a reply that never comes."""
    fail_job(job["id"], message, claim_token)
    if job.get("job_type") != "process_reel":
        return
    try:
        from app.services import nudge

        nudge.fire(job["user_id"], "reel_failed")
    except Exception:
        pass


def process_job(job: dict):
    claim_token = job.get("started_at") or None
    timeout_seconds = job_timeout_seconds(job["job_type"])

    # Shelves are routed BEFORE the processor on a library rebuild, not after.
    # The processor re-runs the whole legacy pipeline and on a real library it
    # exceeds the 600s timeout, which fails the job and returns early — so
    # hanging routing off its success meant the shelves never built at all,
    # no matter how many times the rebuild was triggered. Routing needs only
    # deep_search_documents, which already exist, so it does not depend on
    # that script finishing.
    if job["job_type"] == "rebuild_library":
        rebuild_shelves_for(job["user_id"])

    # Set when the processor ended badly (non-zero exit, timeout) AFTER it had
    # already finished the reel itself. Kept on the job row for diagnosis.
    late_failure = ""
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
        result = run_processor(cmd, timeout_seconds)
    except subprocess.TimeoutExpired:
        late_failure = f"Processor timed out after {timeout_seconds}s"
        if not reel_is_finished(job):
            fail_reel_job(job, late_failure, claim_token)
            return
        result = None
    except Exception as exc:
        detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        fail_reel_job(job, f"Worker error: {detail}", claim_token)
        return

    if result is not None and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Processor failed"
        # The reel is read, marked completed and has its items; what crashed is
        # a whole-library step that runs afterwards. Failing the job here threw
        # away a finished reel, paid for the extraction again on every retry
        # and never told the owner their library was ready.
        if reel_is_finished(job):
            late_failure = message
        elif is_quota_failure(message):
            pause_queue_for_quota(job["id"], claim_token)
            return
        else:
            fail_reel_job(job, message, claim_token)
            return

    if job["job_type"] == "process_reel":
        reel = get_reel_by_id(job["reel_id"])
        if not reel:
            fail_job(job["id"], "Missing reel after processing", claim_token)
            return
        if reel.get("status") != "completed":
            summary = failure_summary_for_reel(job["reel_id"])
            if is_quota_failure(summary):
                pause_queue_for_quota(job["id"], claim_token)
                return
            fail_reel_job(job, summary, claim_token)
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

    # A freshly processed reel gets routed onto the shelves here, reading the
    # documents rebuilt just above. Library rebuilds already routed before the
    # processor ran, since they must not depend on it finishing.
    if job["job_type"] != "rebuild_library":
        rebuild_shelves_for(job["user_id"])

    # Auto-route the freshly-processed reel into the user's smart folders.
    # Wrapped so a routing failure can NEVER fail reel processing. No-op for
    # users with no folders (the loop just doesn't run).
    if job["job_type"] == "process_reel":
        try:
            from app.services.folders import route_reel

            route_reel(job["user_id"], job["reel_id"])
        except Exception:
            pass

    complete_job(job["id"], claim_token, note=late_failure)

    # Now that the reel has a title and media, tell the owner - this is the
    # first moment their library link would actually show them something.
    # Wrapped so a failed DM can never fail a completed job.
    if job["job_type"] == "process_reel":
        try:
            from app.db.database import get_connection as _conn
            from app.services import nudge

            with _conn() as c:
                row = c.execute(
                    "SELECT item_name FROM reel_items WHERE reel_id = ? AND item_name != '' LIMIT 1",
                    (job["reel_id"],),
                ).fetchone()
            nudge.fire(job["user_id"], "reel_ready", title=(row["item_name"] if row else ""))
        except Exception:
            pass


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
