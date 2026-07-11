import csv
import json
import re
from datetime import datetime
from pathlib import Path
import shutil
from urllib.parse import urlparse

from app.config import settings
from app.db.database import get_connection
from app.services.jobs import job_counts
from app.storage import user_storage_dir


INSTAGRAM_URL_RE = re.compile(
    r"^https?://(?:www\.)?instagram\.com/(?:reel|p)/[A-Za-z0-9_-]+/?(?:\?[^\s]+)?$",
    re.IGNORECASE,
)


def normalize(value: str) -> str:
    return " ".join((value or "").strip().split())


def is_valid_instagram_url(url: str) -> bool:
    return bool(INSTAGRAM_URL_RE.match(normalize(url)))


def extract_shortcode(url: str) -> str:
    path_parts = [part for part in urlparse(normalize(url)).path.split("/") if part]
    return path_parts[-1] if path_parts else ""


def fallback_item_name(row: dict) -> str:
    candidates = [
        row.get("Product Name"),
        row.get("Product Brand"),
        row.get("Secondary Category"),
        row.get("Primary Category"),
    ]
    for candidate in candidates:
        value = normalize(candidate)
        if value:
            return value
    summary = normalize(row.get("Summary"))
    if summary:
        return " ".join(summary.split()[:6]).strip() or "Untitled Reel"
    return "Untitled Reel"


REEL_FIELDNAMES = [
    "id",
    "user_id",
    "url",
    "shortcode",
    "received_at",
    "status",
    "media_status",
    "local_video_path",
    "thumbnail_path",
]


def ensure_storage() -> None:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    settings.videos_dir.mkdir(parents=True, exist_ok=True)
    settings.thumbnails_dir.mkdir(parents=True, exist_ok=True)
    if not settings.reel_urls_csv.exists():
        with settings.reel_urls_csv.open("w", newline="", encoding="utf-8") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=REEL_FIELDNAMES)
            writer.writeheader()


def ensure_user_storage(user_id: str) -> None:
    storage_dir = user_storage_dir(user_id)
    storage_dir.mkdir(parents=True, exist_ok=True)


def user_dashboard_paths(user_id: str) -> dict:
    storage_dir = user_storage_dir(user_id)
    return {
        "storage_dir": str(storage_dir),
        "standard_page": str(storage_dir / "shlok_reels_app.html"),
        "personalized_page": str(storage_dir / "shlok_reels_personalized_app.html"),
        "raw_output": str(storage_dir / "shlok_reels_output.csv"),
        "accumulated_output": str(storage_dir / "shlok_reels_accumulated.csv"),
    }


def _normalize_reel_row(row: dict) -> dict:
    return {
        "id": normalize(row.get("id")),
        "user_id": normalize(row.get("user_id")) or "default",
        "url": normalize(row.get("url")),
        "shortcode": normalize(row.get("shortcode")) or extract_shortcode(row.get("url", "")),
        "received_at": normalize(row.get("received_at")),
        "status": normalize(row.get("status")) or "pending",
        "media_status": normalize(row.get("media_status")) or "not_downloaded",
        "local_video_path": normalize(row.get("local_video_path")),
        "thumbnail_path": normalize(row.get("thumbnail_path")),
    }


def sync_csv_from_db() -> None:
    ensure_storage()
    rows = load_reels()
    with settings.reel_urls_csv.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=REEL_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def next_reel_id() -> str:
    with get_connection() as connection:
        rows = connection.execute("SELECT id FROM reels").fetchall()
    max_number = 0
    for row in rows:
        reel_id = normalize(row["id"])
        if reel_id.startswith("reel_"):
            suffix = reel_id.removeprefix("reel_")
            if suffix.isdigit():
                max_number = max(max_number, int(suffix))
    return f"reel_{max_number + 1}"


def ensure_user(user_id: str) -> str:
    normalized_user = normalize(user_id) or "default"
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO users (id, telegram_user_id, display_name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                normalized_user,
                normalized_user,
                normalized_user.replace("_", " ").title(),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
    return normalized_user


def load_reels(user_id: str | None = None) -> list[dict]:
    query = """
        SELECT id, user_id, url, shortcode, received_at, status, media_status, local_video_path, thumbnail_path
        FROM reels
    """
    params = []
    if user_id:
        query += " WHERE user_id = ?"
        params.append(normalize(user_id))
    query += " ORDER BY received_at ASC, id ASC"

    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
    return [_normalize_reel_row(dict(row)) for row in rows]


def get_reel_by_url(url: str, user_id: str | None = None) -> dict | None:
    normalized_url = normalize(url)
    if not normalized_url:
        return None

    query = """
        SELECT id, user_id, url, shortcode, received_at, status, media_status, local_video_path, thumbnail_path
        FROM reels
        WHERE url = ?
    """
    params = [normalized_url]
    if user_id:
        query += " AND user_id = ?"
        params.append(normalize(user_id))
    query += " ORDER BY received_at DESC, id DESC LIMIT 1"

    with get_connection() as connection:
        row = connection.execute(query, params).fetchone()
    return _normalize_reel_row(dict(row)) if row else None


def append_reel(url: str, user_id: str = "default", source: str = "telegram") -> dict:
    normalized_user = ensure_user(user_id)
    normalized_url = normalize(url)
    shortcode = extract_shortcode(normalized_url)
    timestamp = datetime.now().isoformat(timespec="seconds")

    with get_connection() as connection:
        existing = connection.execute(
            """
            SELECT id, user_id, url, shortcode, received_at, status, media_status, local_video_path, thumbnail_path
            FROM reels
            WHERE user_id = ? AND url = ?
            """,
            (normalized_user, normalized_url),
        ).fetchone()
        if existing:
            reel = _normalize_reel_row(dict(existing))
            sync_csv_from_db()
            return reel

        reel = {
            "id": next_reel_id(),
            "user_id": normalized_user,
            "url": normalized_url,
            "shortcode": shortcode,
            "received_at": timestamp,
            "status": "pending",
            "media_status": "not_downloaded",
            "local_video_path": "",
            "thumbnail_path": "",
        }
        connection.execute(
            """
            INSERT INTO reels (
                id, user_id, url, shortcode, received_at, status, media_status,
                local_video_path, thumbnail_path, source, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reel["id"],
                reel["user_id"],
                reel["url"],
                reel["shortcode"],
                reel["received_at"],
                reel["status"],
                reel["media_status"],
                reel["local_video_path"],
                reel["thumbnail_path"],
                normalize(source) or "telegram",
                timestamp,
                timestamp,
            ),
        )
    sync_csv_from_db()
    return reel


def delete_reel(reel_id: str) -> bool:
    normalized_reel_id = normalize(reel_id)
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, local_video_path, thumbnail_path
            FROM reels
            WHERE id = ?
            LIMIT 1
            """,
            (normalized_reel_id,),
        ).fetchone()
        if not row:
            return False

        item_ids = [
            item_row["id"]
            for item_row in connection.execute(
                "SELECT id FROM reel_items WHERE reel_id = ?",
                (normalized_reel_id,),
            ).fetchall()
        ]
        if item_ids:
            placeholders = ",".join("?" for _ in item_ids)
            connection.execute(
                f"DELETE FROM product_links WHERE reel_item_id IN ({placeholders})",
                item_ids,
            )
        connection.execute("DELETE FROM reel_items WHERE reel_id = ?", (normalized_reel_id,))
        connection.execute("DELETE FROM processing_jobs WHERE reel_id = ?", (normalized_reel_id,))
        cursor = connection.execute("DELETE FROM reels WHERE id = ?", (normalized_reel_id,))
        deleted = cursor.rowcount > 0
    if deleted:
        for path_value in (row["local_video_path"], row["thumbnail_path"]):
            normalized_path = normalize(path_value)
            if not normalized_path:
                continue
            path = Path(normalized_path)
            if path.exists() and path.is_file():
                path.unlink(missing_ok=True)
        sync_csv_from_db()
    return deleted


def delete_failed_reels(user_id: str | None = None) -> dict:
    """Delete every reel currently in the 'failed' state (optionally per user).

    Removes the reel rows plus their dependent records (reel_items,
    product_links, processing_jobs) and best-effort deletes any local media,
    then syncs the CSV mirror once. Returns counts so callers can log/report.
    """
    normalized_user = normalize(user_id) if user_id else None
    with get_connection() as connection:
        query = "SELECT id, local_video_path, thumbnail_path FROM reels WHERE status = 'failed'"
        params: list = []
        if normalized_user:
            query += " AND user_id = ?"
            params.append(normalized_user)
        rows = connection.execute(query, params).fetchall()
        reel_ids = [row["id"] for row in rows]
        media_paths = [
            row[column]
            for row in rows
            for column in ("local_video_path", "thumbnail_path")
        ]
        deleted = 0
        if reel_ids:
            placeholders = ",".join("?" for _ in reel_ids)
            item_ids = [
                item_row["id"]
                for item_row in connection.execute(
                    f"SELECT id FROM reel_items WHERE reel_id IN ({placeholders})",
                    reel_ids,
                ).fetchall()
            ]
            if item_ids:
                item_placeholders = ",".join("?" for _ in item_ids)
                connection.execute(
                    f"DELETE FROM product_links WHERE reel_item_id IN ({item_placeholders})",
                    item_ids,
                )
            connection.execute(f"DELETE FROM reel_items WHERE reel_id IN ({placeholders})", reel_ids)
            connection.execute(f"DELETE FROM processing_jobs WHERE reel_id IN ({placeholders})", reel_ids)
            cursor = connection.execute(f"DELETE FROM reels WHERE id IN ({placeholders})", reel_ids)
            deleted = cursor.rowcount

    deleted_media_files = 0
    if deleted:
        for path_value in media_paths:
            normalized_path = normalize(path_value)
            if not normalized_path:
                continue
            path = Path(normalized_path)
            if path.exists() and path.is_file():
                path.unlink(missing_ok=True)
                deleted_media_files += 1
        sync_csv_from_db()
    return {"deleted_reel_count": deleted, "deleted_media_files": deleted_media_files}


def purge_failed_reels_once(flag: str = "purge_failed_reels_v1") -> dict:
    """Run a one-time cleanup of all failed reels, guarded by a maintenance flag.

    Safe to call on every startup: the delete happens only the first time a
    given `flag` is seen (i.e. once per deploy that bumps the flag value), so
    repeated Render restarts do not keep wiping newly-failed reels.
    """
    with get_connection() as connection:
        already = connection.execute(
            "SELECT 1 FROM maintenance_flags WHERE flag = ? LIMIT 1",
            (flag,),
        ).fetchone()
    if already:
        return {"ran": False, "deleted_reel_count": 0, "deleted_media_files": 0}

    result = delete_failed_reels()
    with get_connection() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO maintenance_flags (flag, executed_at) VALUES (?, ?)",
            (flag, datetime.now().isoformat(timespec="seconds")),
        )
    return {"ran": True, **result}


def _clear_user_storage_outputs(user_id: str) -> None:
    storage_dir = user_storage_dir(user_id)
    if not storage_dir.exists():
        return
    for child in storage_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def invalidate_user_library_outputs(user_id: str) -> dict:
    storage_dir = user_storage_dir(user_id)
    if not storage_dir.exists():
        return {"deleted_output_file_count": 0}

    removable_names = {
        "shlok_reels_list_titles_with_items.csv",
        "shlok_reels_list_title_accumulation.csv",
        "shlok_reels_accumulated.csv",
        "shlok_reels_cleaned.csv",
        "shlok_reels_topic_merge_mapping.csv",
        "shlok_reels_topic_graph.json",
        "shlok_reels_personalized_view.json",
        "shlok_reels_aggregation_debug.jsonl",
        "shlok_reels_app.html",
        "shlok_reels_personalized_app.html",
        "pipeline_status.json",
    }

    deleted = 0
    for path in storage_dir.iterdir():
        if path.is_file() and path.name in removable_names:
            path.unlink(missing_ok=True)
            deleted += 1
    return {"deleted_output_file_count": deleted}


def reset_user_library(user_id: str) -> dict:
    normalized_user = normalize(user_id) or "default"
    reels = load_reels(user_id=normalized_user)
    deleted_media_files = 0

    with get_connection() as connection:
        reel_ids = [row["id"] for row in reels]
        media_paths = []
        for reel in reels:
            for path_value in (reel.get("local_video_path"), reel.get("thumbnail_path")):
                normalized_path = normalize(path_value)
                if normalized_path:
                    media_paths.append(Path(normalized_path))

        if reel_ids:
            placeholders = ",".join("?" for _ in reel_ids)
            item_ids = [
                row["id"]
                for row in connection.execute(
                    f"SELECT id FROM reel_items WHERE reel_id IN ({placeholders})",
                    reel_ids,
                ).fetchall()
            ]
            if item_ids:
                item_placeholders = ",".join("?" for _ in item_ids)
                connection.execute(
                    f"DELETE FROM product_links WHERE reel_item_id IN ({item_placeholders})",
                    item_ids,
                )
            connection.execute(
                f"DELETE FROM reel_items WHERE reel_id IN ({placeholders})",
                reel_ids,
            )
            connection.execute(
                f"DELETE FROM reels WHERE id IN ({placeholders})",
                reel_ids,
            )

        connection.execute(
            "DELETE FROM processing_jobs WHERE user_id = ?",
            (normalized_user,),
        )

    for path in media_paths:
        if path.exists() and path.is_file():
            path.unlink(missing_ok=True)
            deleted_media_files += 1

    _clear_user_storage_outputs(normalized_user)
    sync_csv_from_db()

    return {
        "user_id": normalized_user,
        "deleted_reel_count": len(reels),
        "deleted_media_file_count": deleted_media_files,
    }


def reset_reel_for_retry(reel_id: str) -> dict | None:
    reel = get_reel_by_id(reel_id)
    if not reel:
        return None
    for path_value in (reel.get("local_video_path"), reel.get("thumbnail_path")):
        normalized_path = normalize(path_value)
        if not normalized_path:
            continue
        path = Path(normalized_path)
        if path.exists() and path.is_file():
            path.unlink(missing_ok=True)

    timestamp = datetime.now().isoformat(timespec="seconds")
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE reels
            SET status = 'pending', media_status = 'not_downloaded',
                local_video_path = '', thumbnail_path = '', updated_at = ?
            WHERE id = ?
            """,
            (timestamp, normalize(reel_id)),
        )
    sync_csv_from_db()
    return get_reel_by_id(reel_id)


def update_reel_status(url: str, status: str) -> None:
    normalized_url = normalize(url)
    if not normalized_url:
        return
    timestamp = datetime.now().isoformat(timespec="seconds")
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE reels
            SET status = ?, updated_at = ?
            WHERE url = ?
            """,
            (normalize(status) or "pending", timestamp, normalized_url),
        )
    sync_csv_from_db()


def update_reel_media(url: str, media_status: str, local_video_path: str = "", thumbnail_path: str = "") -> None:
    normalized_url = normalize(url)
    if not normalized_url:
        return
    timestamp = datetime.now().isoformat(timespec="seconds")
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE reels
            SET media_status = ?, local_video_path = ?, thumbnail_path = ?, updated_at = ?
            WHERE url = ?
            """,
            (
                normalize(media_status) or "not_downloaded",
                normalize(local_video_path),
                normalize(thumbnail_path),
                timestamp,
                normalized_url,
            ),
        )
    sync_csv_from_db()


def upsert_reel_processing_diagnostics(url: str, payload: dict | None) -> None:
    normalized_url = normalize(url)
    if not normalized_url or not isinstance(payload, dict):
        return
    reel = get_reel_by_url(normalized_url)
    if not reel:
        return
    timestamp = datetime.now().isoformat(timespec="seconds")
    metadata = payload.get("metadata_json")
    if not isinstance(metadata, str):
        metadata = json.dumps(payload.get("metadata", {}), ensure_ascii=False)
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT * FROM reel_processing_diagnostics WHERE reel_id = ? LIMIT 1",
            (reel["id"],),
        ).fetchone()
        existing = dict(existing) if existing else {}

        def pick(key: str, default=""):
            value = payload.get(key)
            if value in {None, ""}:
                return existing.get(key, default)
            return value

        connection.execute(
            """
            INSERT INTO reel_processing_diagnostics (
                reel_id, user_id, url, caption_present, hashtags_present, creator_present,
                transcript_present, transcript_status, transcript_model, transcript_attempts,
                transcript_error, audio_download_status, video_download_status,
                visual_present, visual_status, visual_error,
                media_upload_status, r2_video_uploaded, r2_thumbnail_uploaded,
                processing_version, metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(reel_id) DO UPDATE SET
                user_id = excluded.user_id,
                url = excluded.url,
                caption_present = excluded.caption_present,
                hashtags_present = excluded.hashtags_present,
                creator_present = excluded.creator_present,
                transcript_present = excluded.transcript_present,
                transcript_status = excluded.transcript_status,
                transcript_model = excluded.transcript_model,
                transcript_attempts = excluded.transcript_attempts,
                transcript_error = excluded.transcript_error,
                audio_download_status = excluded.audio_download_status,
                video_download_status = excluded.video_download_status,
                visual_present = excluded.visual_present,
                visual_status = excluded.visual_status,
                visual_error = excluded.visual_error,
                media_upload_status = excluded.media_upload_status,
                r2_video_uploaded = excluded.r2_video_uploaded,
                r2_thumbnail_uploaded = excluded.r2_thumbnail_uploaded,
                processing_version = excluded.processing_version,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                reel["id"],
                reel["user_id"],
                normalized_url,
                1 if str(pick("caption_present", existing.get("caption_present", 0))).lower() in {"1", "true", "yes"} else 0,
                1 if str(pick("hashtags_present", existing.get("hashtags_present", 0))).lower() in {"1", "true", "yes"} else 0,
                1 if str(pick("creator_present", existing.get("creator_present", 0))).lower() in {"1", "true", "yes"} else 0,
                1 if str(pick("transcript_present", existing.get("transcript_present", 0))).lower() in {"1", "true", "yes"} else 0,
                normalize(pick("transcript_status", existing.get("transcript_status", ""))),
                normalize(pick("transcript_model", existing.get("transcript_model", ""))),
                int(pick("transcript_attempts", existing.get("transcript_attempts", 0)) or 0),
                normalize(pick("transcript_error", existing.get("transcript_error", ""))),
                normalize(pick("audio_download_status", existing.get("audio_download_status", ""))),
                normalize(pick("video_download_status", existing.get("video_download_status", ""))),
                1 if str(pick("visual_present", existing.get("visual_present", 0))).lower() in {"1", "true", "yes"} else 0,
                normalize(pick("visual_status", existing.get("visual_status", ""))),
                normalize(pick("visual_error", existing.get("visual_error", ""))),
                normalize(pick("media_upload_status", existing.get("media_upload_status", ""))),
                1 if str(pick("r2_video_uploaded", existing.get("r2_video_uploaded", 0))).lower() in {"1", "true", "yes"} else 0,
                1 if str(pick("r2_thumbnail_uploaded", existing.get("r2_thumbnail_uploaded", 0))).lower() in {"1", "true", "yes"} else 0,
                normalize(pick("processing_version", existing.get("processing_version", ""))),
                metadata if metadata != "{}" else existing.get("metadata_json", "{}"),
                existing.get("created_at", timestamp),
                timestamp,
            ),
        )


def sync_reel_items_from_accumulated(user_id: str, accumulated_csv_path: str | Path) -> None:
    accumulated_path = Path(accumulated_csv_path)
    normalized_user = normalize(user_id) or "default"
    reel_rows = load_reels(user_id=normalized_user)
    reel_ids = [row["id"] for row in reel_rows]
    reels_by_url = {(row.get("url") or "").strip(): row["id"] for row in reel_rows if (row.get("url") or "").strip()}

    with get_connection() as connection:
        if reel_ids:
            placeholders = ",".join("?" for _ in reel_ids)
            item_ids = [
                row["id"]
                for row in connection.execute(
                    f"SELECT id FROM reel_items WHERE reel_id IN ({placeholders})",
                    reel_ids,
                ).fetchall()
            ]
            if item_ids:
                item_placeholders = ",".join("?" for _ in item_ids)
                connection.execute(
                    f"DELETE FROM product_links WHERE reel_item_id IN ({item_placeholders})",
                    item_ids,
                )
            connection.execute(
                f"DELETE FROM reel_items WHERE reel_id IN ({placeholders})",
                reel_ids,
            )

        if not accumulated_path.exists():
            return

        with accumulated_path.open(newline="", encoding="utf-8") as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                url = normalize(row.get("URL"))
                reel_id = reels_by_url.get(url)
                item_name = normalize(row.get("Item Name")) or fallback_item_name(row)
                if not reel_id:
                    continue

                connection.execute(
                    """
                    INSERT INTO reel_items (
                        reel_id, primary_category, secondary_category, item_name, summary, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        reel_id,
                        normalize(row.get("Primary Category")),
                        normalize(row.get("Secondary Category") or row.get("Folder")),
                        item_name,
                        normalize(row.get("Summary")),
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                reel_item_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                contains_product = normalize(row.get("Contains Product")).lower()
                has_product_data = contains_product in {"yes", "true"} or any(
                    normalize(row.get(field))
                    for field in [
                        "Product Name",
                        "Product Brand",
                        "Product Model",
                        "Product Type",
                        "Product Search Query",
                        "Best Buy Link",
                        "Amazon Link",
                        "Flipkart Link",
                        "Nykaa Link",
                    ]
                )
                if has_product_data:
                    connection.execute(
                        """
                        INSERT INTO product_links (
                            reel_item_id, product_name, brand, model, product_type, search_query,
                            best_buy_link, amazon_link, flipkart_link, nykaa_link
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            reel_item_id,
                            normalize(row.get("Product Name")),
                            normalize(row.get("Product Brand")),
                            normalize(row.get("Product Model")),
                            normalize(row.get("Product Type")),
                            normalize(row.get("Product Search Query")),
                            normalize(row.get("Best Buy Link")),
                            normalize(row.get("Amazon Link")),
                            normalize(row.get("Flipkart Link")),
                            normalize(row.get("Nykaa Link")),
                        ),
                    )


def sync_reel_diagnostics_from_accumulated(user_id: str, accumulated_csv_path: str | Path) -> None:
    accumulated_path = Path(accumulated_csv_path)
    if not accumulated_path.exists():
        return
    normalized_user = normalize(user_id) or "default"
    reels_by_url = {
        (row.get("url") or "").strip(): row
        for row in load_reels(user_id=normalized_user)
        if (row.get("url") or "").strip()
    }
    seen_urls = set()

    def metadata_from_row(row: dict) -> dict:
        metadata = {
            "secondary_category": normalize(row.get("Secondary Category")),
            "item_name": normalize(row.get("Item Name")),
        }
        csv_to_metadata = {
            "Creator": "creator",
            "Caption": "caption",
            "Hashtags": "hashtags",
            "Transcript": "transcript",
            "Main Subject": "main_subject",
            "Main Subject Type": "main_subject_type",
            "Inferred Main Theme": "inferred_main_theme",
            "Relevant Visible Text": "relevant_visible_text",
            "Relevant Visual Entities": "relevant_visual_entities",
            "Visual Supporting Points": "visual_supporting_points",
            "Overall Visual Summary": "overall_visual_summary",
        }
        for csv_key, metadata_key in csv_to_metadata.items():
            value = normalize(row.get(csv_key))
            if value:
                metadata[metadata_key] = value
        return metadata

    with accumulated_path.open(newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            url = normalize(row.get("URL"))
            if not url or url in seen_urls or url not in reels_by_url:
                continue
            seen_urls.add(url)
            upsert_reel_processing_diagnostics(
                url,
                {
                    "caption_present": row.get("Caption Present", ""),
                    "hashtags_present": row.get("Hashtags Present", ""),
                    "creator_present": row.get("Creator Present", ""),
                    "transcript_present": row.get("Transcript Present", ""),
                    "transcript_status": row.get("Transcript Status", ""),
                    "transcript_model": row.get("Transcript Model", ""),
                    "transcript_attempts": row.get("Transcript Attempts", ""),
                    "transcript_error": row.get("Transcript Error", ""),
                    "audio_download_status": row.get("Audio Download Status", ""),
                    "video_download_status": row.get("Video Download Status", ""),
                    "visual_present": row.get("Visual Present", ""),
                    "visual_status": row.get("Visual Status", ""),
                    "visual_error": row.get("Visual Error", ""),
                    "processing_version": row.get("Processing Version", ""),
                    "metadata": metadata_from_row(row),
                },
            )


def get_reel_by_id(reel_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, user_id, url, shortcode, received_at, status, media_status, local_video_path, thumbnail_path
            FROM reels
            WHERE id = ?
            LIMIT 1
            """,
            (normalize(reel_id),),
        ).fetchone()
    return _normalize_reel_row(dict(row)) if row else None


def load_reel_processing_diagnostics(user_id: str | None = None) -> list[dict]:
    query = """
        SELECT *
        FROM reel_processing_diagnostics
    """
    params = []
    if user_id:
        query += " WHERE user_id = ?"
        params.append(normalize(user_id))
    query += " ORDER BY updated_at DESC, reel_id DESC"
    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def load_dashboard_status(user_id: str | None = None) -> dict:
    rows = load_reels(user_id=user_id)
    counts = job_counts(user_id=user_id)
    paths = user_dashboard_paths(user_id or "default")
    status_file = Path(paths["storage_dir"]) / "pipeline_status.json"
    raw_output_path = Path(paths["raw_output"])
    item_count = 0
    if raw_output_path.exists():
        with raw_output_path.open(newline="", encoding="utf-8") as infile:
            item_count = sum(1 for _ in csv.DictReader(infile))
    last_updated = ""
    if raw_output_path.exists():
        last_updated = datetime.fromtimestamp(raw_output_path.stat().st_mtime).isoformat(timespec="seconds")
    completed_count = len([row for row in rows if row.get("status") == "completed"])
    failed_count = len([row for row in rows if row.get("status") == "failed"])
    pending_count = len(rows) - completed_count - failed_count
    diagnostics = load_reel_processing_diagnostics(user_id=user_id)
    transcript_success_count = sum(1 for row in diagnostics if row.get("transcript_present"))
    visual_success_count = sum(1 for row in diagnostics if row.get("visual_present"))
    media_upload_success_count = sum(1 for row in diagnostics if normalize(row.get("media_upload_status")) == "uploaded")
    if not status_file.exists():
        return {
            "url_count": len(rows),
            "processed_url_count": completed_count,
            "pending_url_count": pending_count,
            "failed_url_count": failed_count,
            "running_job_count": counts["running"],
            "queued_job_count": counts["pending"],
            "item_count": item_count,
            "last_updated": last_updated,
            "standard_page": paths["standard_page"],
            "personalized_page": paths["personalized_page"],
            "raw_output": paths["raw_output"],
            "accumulated_output": paths["accumulated_output"],
            "storage_mode": "sqlite_with_csv_sync",
            "media_mode": "local_file_storage",
            "diagnostics_count": len(diagnostics),
            "transcript_success_count": transcript_success_count,
            "visual_success_count": visual_success_count,
            "media_upload_success_count": media_upload_success_count,
        }
    if status_file.exists():
        payload = json.loads(status_file.read_text(encoding="utf-8"))
    else:
        payload = {}
    payload["url_count"] = len(rows)
    payload["processed_url_count"] = completed_count
    payload["pending_url_count"] = pending_count
    payload["failed_url_count"] = failed_count
    payload["running_job_count"] = counts["running"]
    payload["queued_job_count"] = counts["pending"]
    payload["item_count"] = item_count
    payload["last_updated"] = last_updated
    payload.setdefault("standard_page", paths["standard_page"])
    payload.setdefault("personalized_page", paths["personalized_page"])
    payload.setdefault("raw_output", paths["raw_output"])
    payload.setdefault("accumulated_output", paths["accumulated_output"])
    payload.setdefault("storage_mode", "sqlite_with_csv_sync")
    payload.setdefault("media_mode", "local_file_storage")
    payload["diagnostics_count"] = len(diagnostics)
    payload["transcript_success_count"] = transcript_success_count
    payload["visual_success_count"] = visual_success_count
    payload["media_upload_success_count"] = media_upload_success_count
    return payload
