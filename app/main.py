import threading
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.deep_search import router as deep_search_router
from app.api.routes.discover import router as discover_router
from app.api.routes.folders import router as folders_router
from app.api.routes.diagnostics import router as diagnostics_router
from app.api.routes.health import router as health_router
from app.api.routes.instagram import router as instagram_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.library import router as library_router
from app.api.routes.personalization_v2 import router as personalization_v2_router
from app.api.routes.reels import router as reels_router
from app.api.routes.telegram import router as telegram_router
from app.api.routes.webapp import router as webapp_router
from app.config import settings
from app.db.init_db import initialize_database


app = FastAPI(
    title="Reel Organizer Backend",
    description="Backend for linked-account reel ingest, library management, and personalized saved-reel organization.",
    version="0.1.0",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.session_https_only,
    same_site="lax",
    session_cookie="reel_app_session",
)


def _queue_janitor_loop():
    """Keep the job queue moving without depending on anyone opening the app.

    The worker dies with every deploy/restart/OOM; previously only a page load
    resurrected it, so an unattended instance sat idle with pending jobs. This
    loop recovers orphans, backfills missing jobs, and restarts the worker a
    few times per hour. The initial sleep lets boot settle before any heavy
    work starts (important on a 512MB instance that may have just OOM'd).
    """
    time.sleep(20)
    tick = 0
    while True:
        try:
            # Disk-space sweep first: on a full disk nothing else (locks, DB
            # writes, worker spawns) can work. Every 10th tick thereafter to
            # mop up videos left behind by processed jobs.
            if tick % 10 == 0:
                import subprocess
                import sys as _sys

                cleanup_script = settings.worker_script.parent / "cleanup_videos.py"
                subprocess.Popen([_sys.executable, str(cleanup_script)])
        except Exception as exc:
            print(f"[janitor] cleanup spawn failed: {exc}", flush=True)
        try:
            from app.services.jobs import ensure_background_progress, maybe_spawn_media_repair

            ensure_background_progress()
            maybe_spawn_media_repair()
        except Exception as exc:
            print(f"[janitor] pass failed: {exc}", flush=True)
        tick += 1
        time.sleep(150)


@app.on_event("startup")
def startup_event():
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    settings.thumbnails_dir.mkdir(parents=True, exist_ok=True)
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    initialize_database()
    # One-time cleanup: purge all failed reels so the queue starts clean.
    # Guarded by a maintenance flag, so it runs once per deploy (bump the flag
    # name to trigger it again), not on every container restart.
    try:
        from app.services.reel_ingest import purge_failed_reels_once

        result = purge_failed_reels_once()
        if result.get("ran"):
            print(f"[startup] purged failed reels: {result}")
    except Exception as exc:
        print(f"[startup] failed-reel purge skipped: {exc}")
    import os

    if os.getenv("QUEUE_JANITOR", "on").strip().lower() != "off":
        threading.Thread(target=_queue_janitor_loop, daemon=True, name="queue-janitor").start()
    else:
        print("[startup] QUEUE_JANITOR=off — background job processing disabled (local dev)")


app.mount("/media", StaticFiles(directory=str(settings.media_dir), check_dir=False), name="media")
# Brand assets (logo, home-screen icons, manifest) shipped with the app code.
app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static"), check_dir=False), name="static")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(webapp_router)
app.include_router(telegram_router)
app.include_router(instagram_router)
app.include_router(reels_router)
app.include_router(jobs_router)
app.include_router(library_router)
app.include_router(dashboard_router)
app.include_router(personalization_v2_router)
app.include_router(deep_search_router)
app.include_router(folders_router)
app.include_router(discover_router)
app.include_router(diagnostics_router)
