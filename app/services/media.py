import logging
from pathlib import Path

import cv2
import yt_dlp

from app.config import settings
from app.services.object_storage import upload_file
from app.services.reel_ingest import (
    extract_shortcode,
    get_reel_by_url,
    update_reel_media,
    upsert_reel_processing_diagnostics,
)


logger = logging.getLogger(__name__)


def _cleanup_existing_files(reel_id: str):
    for existing in settings.videos_dir.glob(f"{reel_id}.*"):
        if existing.is_file():
            existing.unlink(missing_ok=True)
    thumbnail = settings.thumbnails_dir / f"{reel_id}.jpg"
    thumbnail.unlink(missing_ok=True)


def _find_downloaded_video(reel_id: str) -> Path | None:
    candidates = [
        path
        for path in settings.videos_dir.glob(f"{reel_id}.*")
        if path.is_file() and path.suffix.lower() not in {".part", ".ytdl", ".jpg", ".jpeg", ".png"}
    ]
    return candidates[0] if candidates else None


def _make_thumbnail(video_path: Path, reel_id: str) -> Path | None:
    thumbnail_path = settings.thumbnails_dir / f"{reel_id}.jpg"
    cap = cv2.VideoCapture(str(video_path))
    success, frame = cap.read()
    cap.release()
    if not success:
        return None
    cv2.imwrite(str(thumbnail_path), frame)
    return thumbnail_path if thumbnail_path.exists() else None


def _upload_media_to_r2(video_path: Path, thumbnail_path: Path | None) -> dict:
    if not settings.r2_enabled:
        logger.warning("R2 upload skipped because object storage is not enabled in the environment.")
        return {
            "media_upload_status": "r2_disabled",
            "r2_video_uploaded": False,
            "r2_thumbnail_uploaded": False,
        }

    try:
        video_uploaded = upload_file(video_path, f"videos/{video_path.name}", content_type="video/mp4")
        thumbnail_uploaded = False
        if thumbnail_path and thumbnail_path.exists():
            thumbnail_uploaded = upload_file(thumbnail_path, f"thumbnails/{thumbnail_path.name}", content_type="image/jpeg")
        return {
            "media_upload_status": "uploaded" if video_uploaded else "upload_missing_local_file",
            "r2_video_uploaded": bool(video_uploaded),
            "r2_thumbnail_uploaded": bool(thumbnail_uploaded),
        }
    except Exception:
        logger.exception("R2 upload failed for video=%s thumbnail=%s", video_path, thumbnail_path)
        # Keep the local media flow working even if object storage upload fails.
        return {
            "media_upload_status": "upload_failed",
            "r2_video_uploaded": False,
            "r2_thumbnail_uploaded": False,
        }


def ensure_reel_media(url: str) -> dict:
    reel = get_reel_by_url(url)
    if not reel:
        return {"ok": False, "reason": "missing_reel"}

    reel_id = reel["id"]
    shortcode = reel.get("shortcode") or extract_shortcode(url) or reel_id
    existing_video = Path(reel["local_video_path"]) if reel.get("local_video_path") else None
    existing_thumbnail = Path(reel["thumbnail_path"]) if reel.get("thumbnail_path") else None

    if existing_video and existing_video.exists():
        if not existing_thumbnail or not existing_thumbnail.exists():
            thumbnail_path = _make_thumbnail(existing_video, reel_id)
            upload_status = _upload_media_to_r2(existing_video, thumbnail_path)
            update_reel_media(url, "ready", str(existing_video), str(thumbnail_path or ""))
            upsert_reel_processing_diagnostics(url, upload_status)
            return {
                "ok": True,
                "media_status": "ready",
                "local_video_path": str(existing_video),
                "thumbnail_path": str(thumbnail_path or ""),
            }
        upload_status = _upload_media_to_r2(existing_video, existing_thumbnail)
        upsert_reel_processing_diagnostics(url, upload_status)
        return {
            "ok": True,
            "media_status": "ready",
            "local_video_path": str(existing_video),
            "thumbnail_path": str(existing_thumbnail),
        }

    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    settings.thumbnails_dir.mkdir(parents=True, exist_ok=True)
    update_reel_media(url, "downloading", "", "")
    _cleanup_existing_files(reel_id)

    target_template = settings.videos_dir / f"{reel_id}.%(ext)s"

    try:
        with yt_dlp.YoutubeDL(
            {
                "outtmpl": str(target_template),
                "format": "mp4/best",
                "quiet": True,
                "no_warnings": True,
            }
        ) as ydl:
            ydl.download([url])
    except Exception:
        update_reel_media(url, "failed", "", "")
        upsert_reel_processing_diagnostics(url, {"media_upload_status": "download_failed"})
        return {"ok": False, "media_status": "failed", "local_video_path": "", "thumbnail_path": ""}

    video_path = _find_downloaded_video(reel_id)
    if not video_path or not video_path.exists():
        update_reel_media(url, "failed", "", "")
        upsert_reel_processing_diagnostics(url, {"media_upload_status": "download_missing_output"})
        return {"ok": False, "media_status": "failed", "local_video_path": "", "thumbnail_path": ""}

    thumbnail_path = _make_thumbnail(video_path, reel_id)
    upload_status = _upload_media_to_r2(video_path, thumbnail_path)
    update_reel_media(url, "ready", str(video_path), str(thumbnail_path or ""))
    upsert_reel_processing_diagnostics(url, upload_status)
    return {
        "ok": True,
        "media_status": "ready",
        "local_video_path": str(video_path),
        "thumbnail_path": str(thumbnail_path or ""),
        "shortcode": shortcode,
    }
