from typing import Optional

from pydantic import BaseModel, Field


class TelegramIngestRequest(BaseModel):
    url: str = Field(..., min_length=1)
    user_id: Optional[str] = None
    telegram_user_id: Optional[str] = None
    telegram_username: str = ""
    telegram_display_name: str = ""
    source: str = "telegram"


class GoogleLoginRequest(BaseModel):
    credential: str = Field(..., min_length=1)
    csrf_token: str = Field(..., min_length=1)


class UserProfile(BaseModel):
    id: str
    display_name: str = ""
    email: str = ""
    picture_url: str = ""
    telegram_user_id: str = ""
    telegram_username: str = ""


class SessionResponse(BaseModel):
    authenticated: bool = False
    user: Optional[UserProfile] = None
    telegram_connected: bool = False


class TelegramLinkCompleteRequest(BaseModel):
    code: str = Field(..., min_length=1)
    telegram_user_id: str = Field(..., min_length=1)
    telegram_username: str = ""
    telegram_display_name: str = ""


class ReelRecord(BaseModel):
    id: str
    user_id: str = "default"
    url: str
    shortcode: str = ""
    received_at: str
    status: str = "pending"
    media_status: str = "not_downloaded"
    local_video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None


class TelegramIngestResponse(BaseModel):
    ok: bool = True
    id: str
    user_id: str
    url: str
    status: str = "pending"
    job_status: str = "pending"
    saved_to: str


class ProcessingJobRecord(BaseModel):
    id: int
    reel_id: str
    user_id: str
    job_type: str
    status: str
    attempts: int
    error_message: str = ""
    created_at: str
    started_at: str = ""
    finished_at: str = ""
    reel_url: str = ""
    reel_shortcode: str = ""


class LibraryItem(BaseModel):
    reel_id: str = ""
    name: str
    summary: str = ""
    url: str = ""
    contains_product: str = ""
    product_name: str = ""
    product_brand: str = ""
    product_model: str = ""
    product_type: str = ""
    product_search_query: str = ""
    best_buy_link: str = ""
    amazon_link: str = ""
    flipkart_link: str = ""
    nykaa_link: str = ""
    media_status: str = ""
    local_video_path: Optional[str] = None
    local_video_url: Optional[str] = None
    thumbnail_path: Optional[str] = None
    thumbnail_url: Optional[str] = None


class LibraryCollection(BaseModel):
    parent_title: str = ""
    list_title: str
    items: list[LibraryItem]


class LibraryResponse(BaseModel):
    user_id: str
    standard: list[LibraryCollection]
    personalized: list[LibraryCollection]


class HealthResponse(BaseModel):
    ok: bool = True
    service: str
    endpoint: str
    environment: str
    storage_dir: str
    media_dir: str
    csv_file: str
    media_storage_mode: str = "local_only"
    r2_enabled: bool = False


class DashboardResponse(BaseModel):
    url_count: int = 0
    processed_url_count: int = 0
    pending_url_count: int = 0
    failed_url_count: int = 0
    running_job_count: int = 0
    queued_job_count: int = 0
    item_count: int = 0
    last_updated: str = ""
    standard_page: Optional[str] = None
    personalized_page: Optional[str] = None
    raw_output: Optional[str] = None
    accumulated_output: Optional[str] = None
    storage_mode: str = "csv"
    media_mode: str = "local_file_storage"
