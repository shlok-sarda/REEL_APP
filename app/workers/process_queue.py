import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import settings
from app.db.init_db import initialize_database
from app.services.jobs import claim_next_job, complete_job, create_worker_lock, fail_job, release_worker_lock
from app.services.reel_ingest import get_reel_by_id


def process_job(job: dict):
    try:
        if job["job_type"] == "rebuild_library":
            result = subprocess.run(
                [
                    sys.executable,
                    str(settings.processor_script),
                    "--user-id",
                    job["user_id"],
                ],
                cwd=str(settings.processor_script.parent),
                capture_output=True,
                text=True,
                timeout=settings.processor_timeout_seconds,
            )
        else:
            reel = get_reel_by_id(job["reel_id"])
            if not reel:
                fail_job(job["id"], "Missing reel for job")
                return

            result = subprocess.run(
                [
                    sys.executable,
                    str(settings.processor_script),
                    "--user-id",
                    job["user_id"],
                    "--only-url",
                    reel["url"],
                ],
                cwd=str(settings.processor_script.parent),
                capture_output=True,
                text=True,
                timeout=settings.processor_timeout_seconds,
            )
    except subprocess.TimeoutExpired:
        fail_job(job["id"], f"Processor timed out after {settings.processor_timeout_seconds}s")
        return

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Processor failed"
        fail_job(job["id"], message)
        return

    complete_job(job["id"])


def main():
    initialize_database()
    if not create_worker_lock():
        return

    try:
        while True:
            job = claim_next_job()
            if not job:
                break
            process_job(job)
    finally:
        release_worker_lock()


if __name__ == "__main__":
    main()
