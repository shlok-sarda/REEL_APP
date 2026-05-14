import json
from pathlib import Path
from urllib.parse import quote

from app.config import settings
from app.db.database import get_connection
from app.services.object_storage import infer_object_key, presigned_get_url, r2_is_enabled
from app.services.reel_ingest import load_reels, user_dashboard_paths
from render_mobile_knowledge_app import build_collections_from_rows, load_collections
from render_personalized_mobile_app import build_collections as build_personalized_collections
from semantic_personalization import build_outputs as build_semantic_outputs


DEMO_USER_ID = "demo"
LIVE_DEBUG_TITLE_PREFIX = "LIVE CHECK · "

DEMO_ROWS = [
    {
        "Reel ID": "demo_1",
        "Primary Category": "Tech & Gadgets",
        "Secondary Category": "Renewable Energy Tech",
        "Item Name": "Piezoelectric floor tiles",
        "Summary": "Floor tiles that convert footsteps into electricity for lights, displays, and public sensors.",
        "URL": "https://www.instagram.com/reel/DVpFungklSN/",
        "Best Buy Link": "https://www.amazon.in/s?k=piezoelectric+floor+tile",
    },
    {
        "Reel ID": "demo_2",
        "Primary Category": "Tech & Gadgets",
        "Secondary Category": "Audio Accessories",
        "Item Name": "AirPods Ear Hooks",
        "Summary": "Clip-on hooks that make AirPods stay secure during workouts or running.",
        "URL": "https://www.instagram.com/reel/DS2wc8BiIp4/",
        "Best Buy Link": "https://www.amazon.in/s?k=AirPods+ear+hooks",
    },
    {
        "Reel ID": "demo_3",
        "Primary Category": "Tech & Gadgets",
        "Secondary Category": "Science Gadgets",
        "Item Name": "Novium Gravity-Defying Pen",
        "Summary": "A premium pen shown as a gravity-defying object with a striking desk-toy feel.",
        "URL": "https://www.instagram.com/reel/DUTHr4WkXLV/",
        "Best Buy Link": "https://www.amazon.in/s?k=Novium+Gravity-Defying+Pen",
    },
    {
        "Reel ID": "demo_4",
        "Primary Category": "Sports & Hobbies",
        "Secondary Category": "Swimming Technique",
        "Item Name": "Lateral Breathing",
        "Summary": "A step-by-step swimming breathing drill that helps avoid swallowing water.",
        "URL": "https://www.instagram.com/reel/DQu_3mRDZqw/",
    },
    {
        "Reel ID": "demo_5",
        "Primary Category": "Sports & Hobbies",
        "Secondary Category": "Remote Control Cars",
        "Item Name": "Remote Control Drift Car",
        "Summary": "A remote-controlled drift car reel that feels giftable and fun to explore.",
        "URL": "https://www.instagram.com/reel/DRFPKorEXcA/",
        "Best Buy Link": "https://www.amazon.in/s?k=remote+control+drift+car",
    },
    {
        "Reel ID": "demo_6",
        "Primary Category": "Sports & Hobbies",
        "Secondary Category": "Remote Control Cars",
        "Item Name": "Micro Drift Car",
        "Summary": "A tiny but fast drift car shown as a miniature high-performance gadget.",
        "URL": "https://www.instagram.com/reel/DRciUR6jFZX/",
        "Best Buy Link": "https://www.amazon.in/s?k=Legend+of+Toys+Micro+Drift+Car",
    },
    {
        "Reel ID": "demo_7",
        "Primary Category": "Memes & Funny",
        "Secondary Category": "Viral Memes",
        "Item Name": "Khel khatam meme",
        "Summary": "A widely shared meme format used to humorously signal that the game is over.",
        "URL": "https://www.instagram.com/reel/DWJdz3RCr_G/",
    },
    {
        "Reel ID": "demo_8",
        "Primary Category": "Memes & Funny",
        "Secondary Category": "Meme Templates",
        "Item Name": "Ryan Gosling Meme Template",
        "Summary": "A meme template built around Ryan Gosling and the idea of a new character unlocked.",
        "URL": "https://www.instagram.com/reel/DWWd1YkD6Y3/",
    },
    {
        "Reel ID": "demo_9",
        "Primary Category": "Memes & Funny",
        "Secondary Category": "Funny Outfit Moments",
        "Item Name": "Ugly shirts",
        "Summary": "Comedically bad shirts saved for fashion humor and reaction value.",
        "URL": "https://www.instagram.com/reel/DNO8QyNxDSX/",
    },
    {
        "Reel ID": "demo_10",
        "Primary Category": "Food & Culture",
        "Secondary Category": "Indian Street Food",
        "Item Name": "Chicken Kebab Paratha",
        "Summary": "A street-food style chicken kebab paratha wrap with strong visual appetite appeal.",
        "URL": "https://www.instagram.com/reel/DRrmLt0k2Fv/",
        "Best Buy Link": "https://www.amazon.in/s?k=Chicken+Kebab+Paratha",
    },
]


def is_demo_user(user_id: str | None) -> bool:
    return (user_id or "").strip().lower() == DEMO_USER_ID


def _demo_cover_url(title: str) -> str:
    svg = f"""
    <svg xmlns='http://www.w3.org/2000/svg' width='1200' height='800'>
      <defs>
        <linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
          <stop offset='0%' stop-color='#131822'/>
          <stop offset='55%' stop-color='#1d2532'/>
          <stop offset='100%' stop-color='#745f36'/>
        </linearGradient>
      </defs>
      <rect width='100%' height='100%' fill='url(#g)'/>
      <circle cx='1050' cy='160' r='160' fill='rgba(238,215,166,0.14)'/>
      <circle cx='180' cy='650' r='220' fill='rgba(159,213,197,0.10)'/>
      <text x='70' y='130' fill='#9fd5c5' font-size='34' font-family='Arial, sans-serif' font-weight='700'>REEL APP DEMO</text>
      <text x='70' y='420' fill='#f4f6f8' font-size='74' font-family='Arial, sans-serif' font-weight='800'>{title}</text>
    </svg>
    """.strip()
    return "data:image/svg+xml;utf8," + quote(svg)


def _demo_rows_with_media() -> list[dict]:
    rows = []
    for row in DEMO_ROWS:
        clone = dict(row)
        clone["Thumbnail URL"] = _demo_cover_url(clone["Primary Category"])
        clone["Media Status"] = "demo"
        clone["Contains Product"] = "Yes" if clone.get("Best Buy Link") else "No"
        rows.append(clone)
    return rows


def _demo_personalized_collections() -> list[dict]:
    return [
        {
            "parent_title": "Tech & Gadgets",
            "list_title": "Useful Products & Smart Tech",
            "items": [
                {
                    "reel_id": row["Reel ID"],
                    "name": row["Item Name"],
                    "summary": row["Summary"],
                    "url": row["URL"],
                    "best_buy_link": row.get("Best Buy Link", ""),
                    "media_status": "demo",
                    "thumbnail_url": _demo_cover_url("Useful Products"),
                }
                for row in DEMO_ROWS[:3]
            ],
        },
        {
            "parent_title": "Sports & Hobbies",
            "list_title": "Playable Hobby Finds",
            "items": [
                {
                    "reel_id": row["Reel ID"],
                    "name": row["Item Name"],
                    "summary": row["Summary"],
                    "url": row["URL"],
                    "best_buy_link": row.get("Best Buy Link", ""),
                    "media_status": "demo",
                    "thumbnail_url": _demo_cover_url("Playable Hobby Finds"),
                }
                for row in DEMO_ROWS[3:6]
            ],
        },
        {
            "parent_title": "Memes & Funny",
            "list_title": "Quick Laughs",
            "items": [
                {
                    "reel_id": row["Reel ID"],
                    "name": row["Item Name"],
                    "summary": row["Summary"],
                    "url": row["URL"],
                    "media_status": "demo",
                    "thumbnail_url": _demo_cover_url("Quick Laughs"),
                }
                for row in DEMO_ROWS[6:9]
            ],
        },
        {
            "parent_title": "Food & Culture",
            "list_title": "One-Tap Cravings",
            "items": [
                {
                    "reel_id": row["Reel ID"],
                    "name": row["Item Name"],
                    "summary": row["Summary"],
                    "url": row["URL"],
                    "best_buy_link": row.get("Best Buy Link", ""),
                    "media_status": "demo",
                    "thumbnail_url": _demo_cover_url("One-Tap Cravings"),
                }
                for row in DEMO_ROWS[9:10]
            ],
        },
    ]


def _existing_path(path_value: str) -> Path | None:
    path = Path(path_value)
    return path if path.exists() else None


def _media_url_from_path(path_value: str) -> str:
    value = (path_value or "").strip()
    if not value:
        return ""

    if value.startswith(("http://", "https://")):
        return value

    if r2_is_enabled():
        object_key = infer_object_key(value)
        if object_key:
            try:
                return presigned_get_url(object_key)
            except Exception:
                pass

    path = _existing_path(value)
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


def _apply_live_debug_prefix(collections: list[dict]) -> list[dict]:
    updated = []
    for collection in collections:
        clone = dict(collection)
        title = (clone.get("list_title") or "").strip()
        if title and not title.startswith(LIVE_DEBUG_TITLE_PREFIX):
            clone["list_title"] = f"{LIVE_DEBUG_TITLE_PREFIX}{title}"
        updated.append(clone)
    return updated


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


def _db_rows_to_semantic_payload(user_id: str, rows: list[dict]) -> dict:
    semantic_rows = []
    for row in rows:
        semantic_rows.append(
            {
                "URL": row.get("url", ""),
                "Primary Category": row.get("primary_category", ""),
                "Secondary Category": row.get("secondary_category", ""),
                "Umbrella Folder": row.get("primary_category", ""),
                "Folder": row.get("secondary_category", ""),
                "Item Name": row.get("item_name", ""),
                "Summary": row.get("summary", ""),
                "Contains Product": "yes" if any(
                    [
                        row.get("product_name"),
                        row.get("product_brand"),
                        row.get("product_model"),
                        row.get("product_type"),
                        row.get("best_buy_link"),
                        row.get("amazon_link"),
                        row.get("flipkart_link"),
                        row.get("nykaa_link"),
                    ]
                ) else "no",
                "Product Name": row.get("product_name", ""),
                "Product Brand": row.get("product_brand", ""),
                "Product Model": row.get("product_model", ""),
                "Product Type": row.get("product_type", ""),
                "Product Search Query": row.get("product_search_query", ""),
                "Best Buy Link": row.get("best_buy_link", ""),
                "Amazon Link": row.get("amazon_link", ""),
                "Flipkart Link": row.get("flipkart_link", ""),
                "Nykaa Link": row.get("nykaa_link", ""),
                "Media Status": row.get("media_status", ""),
                "Local Video Path": row.get("local_video_path", ""),
                "Local Video URL": "",
                "Thumbnail Path": row.get("thumbnail_path", ""),
                "Thumbnail URL": "",
            }
        )
    return {
        "user_id": user_id,
        "kind": "db_semantic_fallback",
        "row_count": len(semantic_rows),
        "rows": semantic_rows,
    }


def _build_semantic_collections(user_id: str, input_path: Path, storage_dir: Path) -> list[dict]:
    graph, view, _clusters, _debug_logs, _engine = build_semantic_outputs(
        input_path,
        user_id=user_id,
        db_path=settings.database_path,
        force_fallback_embeddings=True,
    )
    graph_file = storage_dir / "shlok_reels_topic_graph.json"
    view_file = storage_dir / "shlok_reels_personalized_view.json"
    graph_file.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    view_file.write_text(json.dumps(view, indent=2), encoding="utf-8")
    return _attach_reel_ids(build_personalized_collections(view, graph), user_id)


def load_standard_collections(user_id: str) -> list[dict]:
    if is_demo_user(user_id):
        return build_collections_from_rows(_demo_rows_with_media())

    db_rows = _db_standard_rows(user_id)
    if db_rows:
        collections = build_collections_from_rows(db_rows)
        return _apply_live_debug_prefix(_attach_reel_ids(collections, user_id))

    paths = user_dashboard_paths(user_id)
    accumulated = _existing_path(paths["accumulated_output"])
    if not accumulated:
        return []
    return _apply_live_debug_prefix(_attach_reel_ids(load_collections(accumulated), user_id))


def load_personalized_collections(user_id: str) -> list[dict]:
    if is_demo_user(user_id):
        return _demo_personalized_collections()

    paths = user_dashboard_paths(user_id)
    view_path = _existing_path(str(Path(paths["storage_dir"]) / "shlok_reels_personalized_view.json"))
    graph_path = _existing_path(str(Path(paths["storage_dir"]) / "shlok_reels_topic_graph.json"))
    if view_path and graph_path:
        view = json.loads(view_path.read_text(encoding="utf-8"))
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        collections = _attach_reel_ids(build_personalized_collections(view, graph), user_id)
        if collections:
            return _apply_live_debug_prefix(collections)

    storage_dir = Path(paths["storage_dir"])
    storage_dir.mkdir(parents=True, exist_ok=True)
    raw_output_path = _existing_path(paths["raw_output"])
    if not raw_output_path:
        db_rows = _db_standard_rows(user_id)
        if not db_rows:
            return []
        payload = _db_rows_to_semantic_payload(user_id, db_rows)
        temp_input = storage_dir / "shlok_reels_semantic_input.json"
        temp_input.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            return _apply_live_debug_prefix(_build_semantic_collections(user_id, temp_input, storage_dir))
        except Exception:
            return []

    try:
        return _apply_live_debug_prefix(_build_semantic_collections(user_id, raw_output_path, storage_dir))
    except Exception:
        return []


def load_library_payload(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "standard": load_standard_collections(user_id),
        "personalized": load_personalized_collections(user_id),
    }


def load_demo_dashboard_payload() -> dict:
    return {
        "url_count": len(DEMO_ROWS),
        "processed_url_count": len(DEMO_ROWS),
        "pending_url_count": 0,
        "failed_url_count": 0,
        "running_job_count": 0,
        "queued_job_count": 0,
        "item_count": len(DEMO_ROWS),
        "last_updated": "2026-05-01T18:00:00",
        "standard_page": None,
        "personalized_page": None,
        "raw_output": None,
        "accumulated_output": None,
        "storage_mode": "demo_seeded_payload",
        "media_mode": "demo_placeholders",
    }
