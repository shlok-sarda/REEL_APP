import os
from pathlib import Path

from app.env import load_local_env


load_local_env()

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


class Settings:
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("PORT", os.getenv("API_PORT", "8000")))
    app_env: str = os.getenv("APP_ENV", "development")
    session_secret: str = os.getenv("SESSION_SECRET", "change-me-before-launch")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "").strip()
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    telegram_bot_username: str = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
    telegram_ingest_secret: str = os.getenv("TELEGRAM_INGEST_SECRET", "").strip()
    instagram_app_username: str = os.getenv("INSTAGRAM_APP_USERNAME", "").strip().lstrip("@")
    instagram_webhook_verify_token: str = os.getenv("INSTAGRAM_WEBHOOK_VERIFY_TOKEN", "").strip()
    instagram_app_secret: str = os.getenv("INSTAGRAM_APP_SECRET", "").strip()
    apify_token: str = os.getenv("APIFY_TOKEN", "").strip()
    meili_host: str = os.getenv("MEILI_HOST", "").strip()
    meili_master_key: str = os.getenv("MEILI_MASTER_KEY", "").strip()
    meili_index: str = os.getenv("MEILI_INDEX", "clipnest_deep_search_reels_staging").strip()
    storage_dir: Path = Path(os.getenv("STORAGE_DIR", PROJECT_ROOT / "Shlok_reels"))
    media_dir: Path = Path(os.getenv("MEDIA_DIR", PROJECT_ROOT / "media" / "Shlok_reels"))
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'final_pipeline' / 'app.db'}")
    r2_bucket_name: str = os.getenv("R2_BUCKET_NAME", "").strip()
    r2_account_id: str = os.getenv("R2_ACCOUNT_ID", "").strip()
    r2_endpoint: str = os.getenv("R2_ENDPOINT", "").strip()
    r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "").strip()
    r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
    processor_script: Path = Path(os.getenv("PROCESSOR_SCRIPT", str(BASE_DIR / "process_shlok_reels.py")))
    worker_script: Path = BASE_DIR / "app" / "workers" / "process_queue.py"
    processor_timeout_seconds: int = int(os.getenv("PROCESSOR_TIMEOUT_SECONDS", "600"))

    @property
    def session_https_only(self) -> bool:
        return self.app_env.lower() in {"production", "staging"} or self.public_base_url.startswith("https://")

    @property
    def r2_enabled(self) -> bool:
        return all(
            [
                self.r2_bucket_name,
                self.r2_account_id,
                self.r2_endpoint,
                self.r2_access_key_id,
                self.r2_secret_access_key,
            ]
        )

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
