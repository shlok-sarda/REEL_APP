import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


class Settings:
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    app_env: str = os.getenv("APP_ENV", "development")
    storage_dir: Path = Path(os.getenv("STORAGE_DIR", PROJECT_ROOT / "Shlok_reels"))
    media_dir: Path = Path(os.getenv("MEDIA_DIR", PROJECT_ROOT / "media" / "Shlok_reels"))
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'final_pipeline' / 'app.db'}")
    processor_script: Path = BASE_DIR / "process_shlok_reels.py"
    worker_script: Path = BASE_DIR / "app" / "workers" / "process_queue.py"
    processor_timeout_seconds: int = int(os.getenv("PROCESSOR_TIMEOUT_SECONDS", "600"))

    @property
    def reel_urls_csv(self) -> Path:
        return self.storage_dir / "reel_urls.csv"

    @property
    def pipeline_status_json(self) -> Path:
        return self.storage_dir / "pipeline_status.json"

    @property
    def raw_output_csv(self) -> Path:
        return self.storage_dir / "shlok_reels_output.csv"

    @property
    def standard_page(self) -> Path:
        return self.storage_dir / "shlok_reels_app.html"

    @property
    def personalized_page(self) -> Path:
        return self.storage_dir / "shlok_reels_personalized_app.html"

    @property
    def thumbnails_dir(self) -> Path:
        return self.media_dir / "thumbnails"

    @property
    def videos_dir(self) -> Path:
        return self.media_dir / "videos"

    @property
    def database_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            return Path(self.database_url.removeprefix("sqlite:///"))
        return PROJECT_ROOT / "final_pipeline" / "app.db"

    @property
    def worker_lock_file(self) -> Path:
        return self.storage_dir / "job_worker.lock"


settings = Settings()
