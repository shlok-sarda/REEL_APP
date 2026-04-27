from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.library import router as library_router
from app.api.routes.reels import router as reels_router
from app.api.routes.telegram import router as telegram_router
from app.api.routes.webapp import router as webapp_router
from app.config import settings
from app.db.init_db import initialize_database


app = FastAPI(
    title="Reel Organizer Backend",
    description="Backend foundation for Telegram reel ingest, dashboard state, and reel management.",
    version="0.1.0",
)


@app.on_event("startup")
def startup_event():
    initialize_database()


app.mount("/media", StaticFiles(directory=str(settings.media_dir)), name="media")

app.include_router(health_router)
app.include_router(webapp_router)
app.include_router(telegram_router)
app.include_router(reels_router)
app.include_router(jobs_router)
app.include_router(library_router)
app.include_router(dashboard_router)
