from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.dashboard import router as dashboard_router
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


@app.on_event("startup")
def startup_event():
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    settings.thumbnails_dir.mkdir(parents=True, exist_ok=True)
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    initialize_database()


app.mount("/media", StaticFiles(directory=str(settings.media_dir), check_dir=False), name="media")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(webapp_router)
app.include_router(telegram_router)
app.include_router(instagram_router)
app.include_router(reels_router)
app.include_router(jobs_router)
app.include_router(library_router)
app.include_router(dashboard_router)
app.include_router(personalization_v2_router)
