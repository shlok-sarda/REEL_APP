import json
from pathlib import Path

from app.config import settings
from app.db.database import get_connection
from app.services.reel_ingest import load_reels, user_dashboard_paths
from render_mobile_knowledge_app import build_collections_from_rows, load_collections
from render_personalized_mobile_app import build_collections as build_personalized_collections


def _existing_path(path_value: str) -> Path | None:
    path = Path(path_value)
    return path if path.exists() else None


def _media_url_from_path(path_value: str) -> str:
    path = _existing_path(path_value)
    if not path:
        return ""
    try:
        relative = path.resolve().relative_to(settings.media_dir.resolve())
    except ValueError:
        return ""
    return "/media/" + "/".join(relative.parts)


def _attach_reel_ids(collections: list[dict], user_id: str) -> list[dict]:
    reels_by_url = {
        (row.get("url") or "").strip(): row
        for row in load_reels(user_id=user_id)
        if (row.get("url") or "").strip()
    }
    filtered_collections = []
    for collection in collections:
        filtered_items = []
        for item in collection.get("items", []):
            reel = reels_by_url.get((item.get("url") or "").strip())
            if not reel:
                continue
            item["reel_id"] = reel.get("id", "")
            item["local_video_url"] = _media_url_from_path(item.get("local_video_path") or reel.get("local_video_path", ""))
            item["thumbnail_url"] = _media_url_from_path(item.get("thumbnail_path") or reel.get("thumbnail_path", ""))
            filtered_items.append(item)
        if filtered_items:
            collection["items"] = filtered_items
            filtered_collections.append(collection)
    return filtered_collections


def _db_standard_rows(user_id: str) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                reels.id AS reel_id,
                reels.url AS url,
                reels.media_status AS media_status,
                reels.local_video_path AS local_video_path,
                reels.thumbnail_path AS thumbnail_path,
                reel_items.primary_category AS primary_category,
                reel_items.secondary_category AS secondary_category,
                reel_items.item_name AS item_name,
                reel_items.summary AS summary,
                product_links.product_name AS product_name,
                product_links.brand AS product_brand,
                product_links.model AS product_model,
                product_links.product_type AS product_type,
                product_links.search_query AS product_search_query,
                product_links.best_buy_link AS best_buy_link,
                product_links.amazon_link AS amazon_link,
                product_links.flipkart_link AS flipkart_link,
                product_links.nykaa_link AS nykaa_link
            FROM reel_items
            JOIN reels ON reels.id = reel_items.reel_id
            LEFT JOIN product_links ON product_links.reel_item_id = reel_items.id
            WHERE reels.user_id = ?
            ORDER BY reel_items.primary_category, reel_items.secondary_category, reel_items.item_name, reels.received_at
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def load_standard_collections(user_id: str) -> list[dict]:
    db_rows = _db_standard_rows(user_id)
    if db_rows:
        collections = build_collections_from_rows(db_rows)
        return _attach_reel_ids(collections, user_id)

    paths = user_dashboard_paths(user_id)
    accumulated = _existing_path(paths["accumulated_output"])
    if not accumulated:
        return []
    return _attach_reel_ids(load_collections(accumulated), user_id)


def load_personalized_collections(user_id: str) -> list[dict]:
    paths = user_dashboard_paths(user_id)
    view_path = _existing_path(str(Path(paths["storage_dir"]) / "shlok_reels_personalized_view.json"))
    graph_path = _existing_path(str(Path(paths["storage_dir"]) / "shlok_reels_topic_graph.json"))
    if not view_path or not graph_path:
        return []
    view = json.loads(view_path.read_text(encoding="utf-8"))
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    return _attach_reel_ids(build_personalized_collections(view, graph), user_id)


def load_library_payload(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "standard": load_standard_collections(user_id),
        "personalized": load_personalized_collections(user_id),
    }
