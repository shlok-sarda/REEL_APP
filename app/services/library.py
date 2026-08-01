import json
import re
import threading
from pathlib import Path
from urllib.parse import quote

from app.config import settings
from app.db.database import get_connection
from app.services.media import ensure_reel_media
from app.services.object_storage import infer_object_key, presigned_get_url, r2_is_enabled
from app.services.personalization_v2.engine import PersonalizationV2Engine
from app.services.personalization_v2.graph_engine import ASSIGNMENT_VERSION as GRAPH_ASSIGNMENT_VERSION
from app.services.personalization_v2.hybrid_router import HYBRID_ASSIGNMENT_VERSION
from app.services.personalization_v2.repository import PersonalizationV2Repository
from app.services.reel_ingest import load_reels, user_dashboard_paths
from render_mobile_knowledge_app import build_collections_from_rows, load_collections
from strong_personalization import build_strong_personalization, load_items as load_strong_personalization_items


DEMO_USER_ID = "demo"

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


_DEMO_PALETTES = [
    ("#1c2b4a", "#3d5a80", "#98c1d9"),
    ("#2d1b3d", "#6d3b6e", "#c98bb9"),
    ("#1b3a2d", "#3f7a5a", "#a3d9b1"),
    ("#3a2a1b", "#7a5a3f", "#d9c1a3"),
    ("#1b2d3a", "#3f5f7a", "#a3c1d9"),
    ("#3a1b1f", "#7a3f4a", "#d9a3ad"),
    ("#26203a", "#4f4478", "#b0a3d9"),
    ("#33301b", "#6e683f", "#d9d3a3"),
]


def _demo_cover_url(title: str) -> str:
    dark, mid, light = _DEMO_PALETTES[sum(ord(char) for char in title) % len(_DEMO_PALETTES)]
    svg = f"""
    <svg xmlns='http://www.w3.org/2000/svg' width='900' height='1600'>
      <defs>
        <linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
          <stop offset='0%' stop-color='{dark}'/>
          <stop offset='60%' stop-color='{mid}'/>
          <stop offset='100%' stop-color='{dark}'/>
        </linearGradient>
      </defs>
      <rect width='100%' height='100%' fill='url(#g)'/>
      <circle cx='740' cy='300' r='260' fill='{light}' opacity='0.16'/>
      <circle cx='160' cy='1280' r='340' fill='{light}' opacity='0.10'/>
      <circle cx='450' cy='800' r='120' fill='{light}' opacity='0.12'/>
    </svg>
    """.strip()
    return "data:image/svg+xml;utf8," + quote(svg)


def _demo_rows_with_media() -> list[dict]:
    rows = []
    for row in DEMO_ROWS:
        clone = dict(row)
        clone["Thumbnail URL"] = _demo_cover_url(clone["Item Name"])
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
                    "thumbnail_url": _demo_cover_url(row["Item Name"]),
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
                    "thumbnail_url": _demo_cover_url(row["Item Name"]),
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
                    "thumbnail_url": _demo_cover_url(row["Item Name"]),
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
                    "thumbnail_url": _demo_cover_url(row["Item Name"]),
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

    path = _existing_path(value)
    if path:
        try:
            relative = path.resolve().relative_to(settings.media_dir.resolve())
            return "/media/" + "/".join(relative.parts)
        except ValueError:
            pass

    if r2_is_enabled():
        object_key = infer_object_key(value)
        if object_key:
            try:
                return presigned_get_url(object_key)
            except Exception:
                pass

    return ""


def _path_value_is_remote(path_value: str) -> bool:
    value = (path_value or "").strip()
    return value.startswith(("http://", "https://"))


def _path_value_exists(path_value: str) -> bool:
    value = (path_value or "").strip()
    if not value:
        return False
    if _path_value_is_remote(value):
        return True
    path = _existing_path(value)
    return bool(path)


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
            # Save-time must reach the client on every path (the CSV fallback
            # has no such column), or "Recently saved" cannot order by it.
            item["received_at"] = item.get("received_at") or reel.get("received_at", "")
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
                reels.received_at AS received_at,
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


def _db_v2_item_rows(user_id: str) -> dict[int, dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                reel_item_features.reel_item_id AS reel_item_id,
                reels.id AS reel_id,
                reels.url AS url,
                reels.media_status AS media_status,
                reels.local_video_path AS local_video_path,
                reels.thumbnail_path AS thumbnail_path,
                reels.received_at AS received_at,
                reel_item_features.item_name AS item_name,
                reel_item_features.summary AS summary,
                reel_item_features.specific_category AS specific_category,
                COALESCE(product_links.product_name, '') AS product_name,
                COALESCE(product_links.brand, '') AS product_brand,
                COALESCE(product_links.model, '') AS product_model,
                COALESCE(product_links.product_type, '') AS product_type,
                COALESCE(product_links.search_query, '') AS product_search_query,
                COALESCE(product_links.best_buy_link, '') AS best_buy_link,
                COALESCE(product_links.amazon_link, '') AS amazon_link,
                COALESCE(product_links.flipkart_link, '') AS flipkart_link,
                COALESCE(product_links.nykaa_link, '') AS nykaa_link
            FROM reel_item_features
            JOIN reels ON reels.id = reel_item_features.reel_id
            LEFT JOIN product_links ON product_links.reel_item_id = reel_item_features.reel_item_id
            WHERE reel_item_features.user_id = ?
            ORDER BY reel_item_features.reel_item_id ASC
            """,
            (user_id,),
        ).fetchall()
    return {int(row["reel_item_id"]): dict(row) for row in rows}


def _build_strong_personalization_collections(user_id: str) -> list[dict]:
    strong_items = load_strong_personalization_items(settings.database_path, user_id)
    if not strong_items:
        return []

    payload = build_strong_personalization(strong_items)
    item_rows_by_id = _db_v2_item_rows(user_id)
    collections = []
    for collection in payload.get("published_lists", []):
        definition = collection.get("definition") or {}
        parent_title = (
            definition.get("canonical_domain")
            or definition.get("family")
            or "Personalized"
        ).strip()
        list_title = (collection.get("title") or "Personalized").strip()
        items = []
        seen = set()
        for strong_item in collection.get("items", []):
            reel_item_id = int(strong_item.get("reel_item_id") or 0)
            item_row = item_rows_by_id.get(reel_item_id, {})
            product_name = item_row.get("product_name") or strong_item.get("product_name", "")
            item = {
                "reel_id": item_row.get("reel_id") or strong_item.get("reel_id", ""),
                "name": item_row.get("item_name") or strong_item.get("item_name") or "Untitled Reel",
                "summary": item_row.get("summary") or strong_item.get("summary") or "",
                "url": item_row.get("url") or strong_item.get("url", ""),
                "contains_product": "Yes" if product_name else "No",
                "product_name": product_name,
                "product_brand": item_row.get("product_brand") or strong_item.get("brand", ""),
                "product_model": item_row.get("product_model", ""),
                "product_type": item_row.get("product_type", ""),
                "product_search_query": item_row.get("product_search_query", ""),
                "best_buy_link": item_row.get("best_buy_link", ""),
                "amazon_link": item_row.get("amazon_link", ""),
                "flipkart_link": item_row.get("flipkart_link", ""),
                "nykaa_link": item_row.get("nykaa_link", ""),
                "media_status": item_row.get("media_status", ""),
                "local_video_path": item_row.get("local_video_path", ""),
                "local_video_url": _media_url_from_path(item_row.get("local_video_path", "")),
                "thumbnail_path": item_row.get("thumbnail_path", ""),
                "thumbnail_url": _media_url_from_path(item_row.get("thumbnail_path", "")),
                "received_at": item_row.get("received_at", ""),
                "membership_score": strong_item.get("membership_score", ""),
                "membership_reasons": strong_item.get("membership_reasons", {}),
                "personalization_model": payload.get("model", ""),
            }
            dedupe_key = (item["reel_id"], item["name"], item["url"])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            items.append(item)
        if items:
            collections.append(
                {
                    "parent_title": parent_title,
                    "list_title": list_title,
                    "items": items,
                    "personalization_model": payload.get("model", ""),
                    "metrics": collection.get("metrics", {}),
                }
            )
    return collections


def _strong_personalization_source_item_count(user_id: str) -> int:
    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM reel_item_features
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
    except Exception:
        return 0
    return int(row["count"] if row else 0)


def _current_reel_item_count(user_id: str) -> int:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM reel_items
            JOIN reels ON reels.id = reel_items.reel_id
            WHERE reels.user_id = ?
            """,
            (user_id,),
        ).fetchone()
    return int(row["count"] if row else 0)


def _current_reel_item_state(user_id: str) -> tuple[int, int]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS count,
                COALESCE(MAX(reel_items.id), 0) AS max_reel_item_id
            FROM reel_items
            JOIN reels ON reels.id = reel_items.reel_id
            WHERE reels.user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return 0, 0
    return int(row["count"] or 0), int(row["max_reel_item_id"] or 0)


def _ensure_v2_media_ready(user_id: str) -> None:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT reels.url, reels.media_status, reels.local_video_path, reels.thumbnail_path
            FROM reels
            JOIN reel_items ON reel_items.reel_id = reels.id
            WHERE reels.user_id = ?
              AND reels.status = 'completed'
            ORDER BY reels.received_at DESC
            """,
            (user_id,),
        ).fetchall()

    for row in rows:
        url = (row["url"] or "").strip()
        media_status = (row["media_status"] or "").strip().lower()
        local_video_path = (row["local_video_path"] or "").strip()
        thumbnail_path = (row["thumbnail_path"] or "").strip()
        if not url:
            continue
        if media_status == "bootstrap":
            continue
        video_ready = _path_value_exists(local_video_path)
        thumbnail_ready = _path_value_exists(thumbnail_path)
        if media_status == "ready" and video_ready and thumbnail_ready:
            continue
        try:
            ensure_reel_media(url)
        except Exception:
            continue


def _load_or_build_v2_snapshot(user_id: str) -> dict:
    repo = PersonalizationV2Repository()
    current_item_count, current_max_reel_item_id = _current_reel_item_state(user_id)
    snapshot = repo.load_debug_snapshot(user_id)
    snapshot_item_ids = [
        int(row.get("reel_item_id") or 0)
        for row in snapshot.get("features", [])
        if row.get("reel_item_id") is not None
    ]
    snapshot_max_reel_item_id = max(snapshot_item_ids, default=0)
    assignment_versions = {
        (row.get("assignment_version") or "").strip()
        for row in snapshot.get("memberships", [])
        if (row.get("assignment_version") or "").strip()
    }
    current_personalization_versions = {GRAPH_ASSIGNMENT_VERSION, HYBRID_ASSIGNMENT_VERSION}
    snapshot_is_outdated = bool(snapshot.get("membership_count")) and assignment_versions.isdisjoint(current_personalization_versions)
    if (
        snapshot.get("feature_count", 0) != current_item_count
        or snapshot_max_reel_item_id != current_max_reel_item_id
        or snapshot_is_outdated
    ):
        # backfill_user starts by wiping every feature, node and membership for
        # the user. Two of those running at once — the background refresh and
        # this inline path both fire on a cold account — means one resets the
        # state the other is mid-way through writing. Only one rebuild at a
        # time; the loser serves the current snapshot and catches up next call.
        with _FEATURE_REFRESH_LOCK:
            if user_id in _FEATURE_REFRESH_IN_FLIGHT:
                return snapshot
            _FEATURE_REFRESH_IN_FLIGHT.add(user_id)
        try:
            engine = PersonalizationV2Engine(repo=repo)
            snapshot = engine.backfill_user(user_id, use_llm=False, use_remote_embeddings=False)
        finally:
            with _FEATURE_REFRESH_LOCK:
                _FEATURE_REFRESH_IN_FLIGHT.discard(user_id)
    return snapshot


def _build_v2_collections(user_id: str) -> list[dict]:
    snapshot = _load_or_build_v2_snapshot(user_id)
    titles_by_cluster = {
        row["cluster_node_id"]: row
        for row in snapshot.get("titles", [])
    }
    features_by_id = {
        int(row["reel_item_id"]): row
        for row in snapshot.get("features", [])
    }
    item_rows_by_id = _db_v2_item_rows(user_id)

    grouped: dict[tuple[str, str], list[dict]] = {}
    memberships_by_cluster: dict[str, list[dict]] = {}
    for membership in snapshot.get("memberships", []):
        memberships_by_cluster.setdefault(membership["cluster_node_id"], []).append(membership)

    cluster_nodes = [
        row
        for row in snapshot.get("nodes", [])
        if row.get("node_type") == "cluster" and int(row.get("save_count", 0) or 0) > 0
    ]
    cluster_nodes.sort(key=lambda row: (-int(row.get("save_count", 0) or 0), (row.get("canonical_key") or "")))

    for cluster in cluster_nodes:
        cluster_id = cluster["id"]
        title = (titles_by_cluster.get(cluster_id, {}) or {}).get("title") or cluster.get("display_hint") or "Untitled"
        metadata = cluster.get("metadata_json") or {}
        parent_title = (metadata.get("canonical_domain") or cluster.get("display_hint") or "Personalized").strip()
        key = (parent_title, title)
        grouped.setdefault(key, [])
        seen = {(row.get("reel_id"), row.get("name"), row.get("url")) for row in grouped[key]}

        members = sorted(
            memberships_by_cluster.get(cluster_id, []),
            key=lambda row: float(row.get("assignment_score", 0.0) or 0.0),
            reverse=True,
        )
        for membership in members:
            reel_item_id = int(membership["reel_item_id"])
            feature = features_by_id.get(reel_item_id, {})
            item_row = item_rows_by_id.get(reel_item_id, {})
            item = {
                "reel_id": item_row.get("reel_id", ""),
                "name": feature.get("item_name") or item_row.get("item_name") or "Untitled Reel",
                "summary": feature.get("summary") or item_row.get("summary") or "",
                "url": feature.get("url") or item_row.get("url") or "",
                "contains_product": "Yes" if item_row.get("product_name") else "No",
                "product_name": item_row.get("product_name", ""),
                "product_brand": item_row.get("product_brand", ""),
                "product_model": item_row.get("product_model", ""),
                "product_type": item_row.get("product_type", ""),
                "product_search_query": item_row.get("product_search_query", ""),
                "best_buy_link": item_row.get("best_buy_link", ""),
                "amazon_link": item_row.get("amazon_link", ""),
                "flipkart_link": item_row.get("flipkart_link", ""),
                "nykaa_link": item_row.get("nykaa_link", ""),
                "media_status": item_row.get("media_status", ""),
                "local_video_path": item_row.get("local_video_path", ""),
                "local_video_url": _media_url_from_path(item_row.get("local_video_path", "")),
                "thumbnail_path": item_row.get("thumbnail_path", ""),
                "thumbnail_url": _media_url_from_path(item_row.get("thumbnail_path", "")),
                "received_at": item_row.get("received_at", ""),
            }
            dedupe_key = (item["reel_id"], item["name"], item["url"])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            grouped[key].append(item)

    collections = [
        {
            "parent_title": parent_title,
            "list_title": list_title,
            "items": items,
        }
        for (parent_title, list_title), items in grouped.items()
        if items
    ]
    merged_by_title: dict[str, dict] = {}
    generic_parent_titles = {"", "Miscellaneous", "Generic", "Personalized", "General"}
    for collection in collections:
        title_key = (collection.get("list_title") or "").strip().lower()
        if not title_key:
            continue
        existing = merged_by_title.get(title_key)
        if not existing:
            merged_by_title[title_key] = {
                "parent_title": collection.get("parent_title", ""),
                "list_title": collection.get("list_title", ""),
                "items": list(collection.get("items", [])),
            }
            continue
        existing_parent = (existing.get("parent_title") or "").strip()
        incoming_parent = (collection.get("parent_title") or "").strip()
        if existing_parent in generic_parent_titles and incoming_parent not in generic_parent_titles:
            existing["parent_title"] = incoming_parent
        seen = {(row.get("reel_id"), row.get("name"), row.get("url")) for row in existing["items"]}
        for item in collection.get("items", []):
            dedupe_key = (item.get("reel_id"), item.get("name"), item.get("url"))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            existing["items"].append(item)
    collections = list(merged_by_title.values())
    collections.sort(key=lambda row: (-len(row["items"]), row["parent_title"].lower(), row["list_title"].lower()))
    return collections


def load_standard_collections(user_id: str) -> list[dict]:
    if is_demo_user(user_id):
        return build_collections_from_rows(_demo_rows_with_media())

    db_rows = _db_standard_rows(user_id)
    if db_rows:
        collections = build_collections_from_rows(db_rows)
        return _attach_reel_ids(collections, user_id)

    paths = user_dashboard_paths(user_id)
    accumulated = _existing_path(paths["accumulated_output"])
    if not accumulated:
        return []
    return _attach_reel_ids(load_collections(accumulated), user_id)


def load_personalized_collections(user_id: str, prefer_graph: bool = False) -> list[dict]:
    """Personalized shelves for a user.

    `prefer_graph` picks the clustering engine instead of the rule engine.
    The two produce completely different shelves from the same library — on a
    129-item account the rule engine publishes 1 shelf and the graph engine
    publishes 19 — so which one answers must be a fixed decision, never
    "whichever happened to return something". That fallback is what made the
    shelves appear to reshuffle at random: the rule engine needs features to
    exist, so the first load after any rebuild fell through to the graph
    engine and the whole set changed, then changed back once features landed.
    """
    if is_demo_user(user_id):
        return _demo_personalized_collections()

    builders = (
        (_build_v2_collections, "personalization v2")
        if prefer_graph
        else (_build_strong_personalization_collections, "strong personalization")
    ), (
        (_build_strong_personalization_collections, "strong personalization")
        if prefer_graph
        else (_build_v2_collections, "personalization v2")
    )
    for builder, label in builders:
        try:
            collections = builder(user_id)
            if collections:
                return collections
        except Exception as exc:
            print(f"[library] {label} fallback for {user_id}: {exc}")
    return []


# Shelf titles the clustering engine emits for "everything I could not place".
# They are buckets, not interests — `General` alone held 55 of 129 items.
_GENERIC_SHELF_TITLES = frozenset({
    "general", "generic", "place", "uncertain", "miscellaneous",
    "personalized", "unsorted", "other", "advice", "commentary",
})

# A shelf needs enough saves to be a real repeated interest, and the screen
# needs few enough shelves to be readable. Coverage is deliberately NOT the
# goal — reels that belong to no strong theme stay in Recently saved and
# search rather than padding the list with one-item shelves.
_MIN_SHELF_ITEMS = 3
_MAX_SHELVES = 8


_TITLE_STOPWORDS = frozenset({"in", "the", "and", "of", "a", "at", "for", "&"})

# Two shelves this similar by title are one interest the engine split — almost
# always on location granularity, e.g. "Bangkok Luxury Outlet Shopping" and
# "Thailand Luxury Outlet Shopping", six items each, one shopping trip. Set
# high enough that genuinely different cities stay apart: "Restaurants in Goa"
# vs "Restaurants in Varanasi" scores 0.50 and is left alone.
_TITLE_MERGE_SIMILARITY = 0.60


def _title_tokens(title: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9']+", (title or "").lower()) if token not in _TITLE_STOPWORDS}


def _merge_near_duplicate_shelves(collections: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for collection in collections:
        tokens = _title_tokens(collection.get("list_title", ""))
        target = None
        for candidate in merged:
            shared = tokens & candidate["_tokens"]
            union = tokens | candidate["_tokens"]
            if union and len(shared) / len(union) >= _TITLE_MERGE_SIMILARITY:
                target = candidate
                break
        if not target:
            merged.append({**collection, "_tokens": tokens})
            continue
        # Keep only what both shelves agree on, so the location that split them
        # drops out and the shared theme becomes the name.
        shared = tokens & target["_tokens"]
        words = [word for word in (target.get("list_title") or "").split() if _title_tokens(word) <= shared]
        if words:
            target["list_title"] = " ".join(words)
        target["_tokens"] = shared or target["_tokens"]
        seen = {(i.get("reel_id"), i.get("name"), i.get("url")) for i in target.get("items", [])}
        for item in collection.get("items", []):
            key = (item.get("reel_id"), item.get("name"), item.get("url"))
            if key in seen:
                continue
            seen.add(key)
            target.setdefault("items", []).append(item)
    for collection in merged:
        collection.pop("_tokens", None)
    return merged


def _curate_collections(collections: list[dict]) -> list[dict]:
    kept = []
    for collection in collections:
        title = (collection.get("list_title") or "").strip().lower()
        if title in _GENERIC_SHELF_TITLES:
            continue
        if len(collection.get("items", [])) < _MIN_SHELF_ITEMS:
            continue
        # The UI hides a shelf whose category is a generic bucket, and it reads
        # the parent first — so a good shelf the engine filed under
        # "Miscellaneous" (Apps & Tools, 7 items) never rendered. Drop the
        # useless parent and let the shelf stand on its own name.
        if (collection.get("parent_title") or "").strip().lower() in _GENERIC_SHELF_TITLES:
            collection = {**collection, "parent_title": ""}
        kept.append(collection)
    kept.sort(key=lambda row: (-len(row.get("items", [])), (row.get("list_title") or "").lower()))
    kept = _merge_near_duplicate_shelves(kept)
    kept.sort(key=lambda row: (-len(row.get("items", [])), (row.get("list_title") or "").lower()))
    return kept[:_MAX_SHELVES]


def load_recent_reels(user_id: str, limit: int = 120) -> list[dict]:
    """Authoritative "Recently saved" list, straight from the reels table.

    Ordered strictly by save time (received_at DESC), with created_at and id as
    deterministic tiebreakers so the order NEVER changes between refreshes.
    Deliberately independent of the personalization engine — that engine
    reorders clusters non-deterministically and was dropping received_at, which
    made recents look random. This is the source of truth for "what I saved".
    """
    if is_demo_user(user_id):
        rows = _demo_rows_with_media()
        # Newest-first for the demo: reverse the seed order.
        return [
            {
                "reel_id": row["Reel ID"],
                "name": row["Item Name"],
                "summary": row.get("Summary", ""),
                "url": row.get("URL", ""),
                "thumbnail_url": row.get("Thumbnail URL", ""),
                "received_at": row.get("Received At", ""),
            }
            for row in reversed(rows)
        ][:limit]

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                reels.id AS reel_id,
                reels.url AS url,
                reels.received_at AS received_at,
                reels.local_video_path AS local_video_path,
                reels.thumbnail_path AS thumbnail_path,
                COALESCE(reel_items.item_name, reel_item_features.item_name, '') AS name,
                COALESCE(reel_items.summary, reel_item_features.summary, '') AS summary
            FROM reels
            LEFT JOIN reel_items ON reel_items.reel_id = reels.id
            LEFT JOIN reel_item_features ON reel_item_features.reel_id = reels.id
            WHERE reels.user_id = ?
            GROUP BY reels.id
            ORDER BY reels.received_at DESC, reels.created_at DESC, reels.id DESC
            """,
            (user_id,),
        ).fetchall()

    recents = []
    for row in rows:
        item = dict(row)
        name = (item.get("name") or "").strip()
        # Skip reels that never produced a real item (still processing / failed);
        # they have no title or media to show yet.
        if not name or name.lower() == "processing failed":
            continue
        item["thumbnail_url"] = _media_url_from_path(item.get("thumbnail_path") or "")
        item["local_video_url"] = _media_url_from_path(item.get("local_video_path") or "")
        recents.append(item)
        if len(recents) >= limit:
            break
    return recents


# Founder-curated demo shelves for the promo video (2026-07-25): only these
# exact shelf titles may appear on the demo account; anything else the engine
# produces is dropped there. Temporary hard-coding until the collections
# engine is reworked for confidence-gated shelves.
_DEMO_SHOWCASE_KEEP_TITLES = frozenset({
    "Restaurants in Bali",
    "Exercise & Training",
    "Nature & Weather",
    "Movies",
    "Productivity & Tools",
    "Business & Culture",
})

# A reel contributing more than this many items to one shelf is a caption
# listicle ("20 restaurants in Bali...") — it collapses to a single card.
# Reels with a few genuine items (a two-exercise workout reel) keep them all.
_DEMO_LISTICLE_ITEM_LIMIT = 3


def _curate_demo_showcase_collections(collections: list[dict]) -> list[dict]:
    curated = []
    for collection in collections:
        if collection.get("list_title") not in _DEMO_SHOWCASE_KEEP_TITLES:
            continue
        items = collection.get("items", [])
        counts: dict = {}
        for item in items:
            key = item.get("reel_id") or item.get("url") or item.get("name")
            counts[key] = counts.get(key, 0) + 1
        collapsed: set = set()
        kept = []
        for item in items:
            key = item.get("reel_id") or item.get("url") or item.get("name")
            if counts[key] > _DEMO_LISTICLE_ITEM_LIMIT:
                if key in collapsed:
                    continue
                collapsed.add(key)
            kept.append(item)
        collection["items"] = kept
        curated.append(collection)
    return curated


def _is_demo_showcase_account(user_id: str) -> bool:
    """The real, shared account behind /demo-login — not the fake 'demo' user."""
    email = settings.demo_account_email
    if not email or not user_id:
        return False
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id FROM users WHERE lower(email) = ? LIMIT 1", (email,)
        ).fetchone()
    return bool(row) and row["id"] == user_id


def collections_enabled(user_id: str) -> bool:
    """Who currently sees Collections shelves.

    The demo showcase account (for the promo link) plus anything listed in the
    COLLECTIONS_ACCOUNTS env var, by email or user id. That env var is the
    dial for putting the feature in a real library while its mistakes are
    still being worked out — no deploy needed to add or drop an account.
    """
    if not user_id:
        return False
    if _is_demo_showcase_account(user_id):
        return True
    allowlist = settings.collections_accounts
    if not allowlist:
        return False
    if user_id.strip().lower() in allowlist:
        return True
    with get_connection() as connection:
        row = connection.execute(
            "SELECT lower(email) AS email FROM users WHERE id = ? LIMIT 1", (user_id,)
        ).fetchone()
    return bool(row) and (row["email"] or "") in allowlist


# Features are written ONLY by the personalization backfill, and that backfill
# is only reachable when the strong-personalization engine returns nothing.
# Once it publishes even one shelf the backfill stops running, so reels saved
# after that never get features and never reach Collections. These accounts
# are the ones actually evaluating the shelves, so keep their features in step
# with their library — off the request thread, because a full rebuild takes
# ~16s for 129 items and the UI already re-polls every 8-25s.
_FEATURE_REFRESH_LOCK = threading.Lock()
_FEATURE_REFRESH_IN_FLIGHT: set[str] = set()

# Last non-empty shelf set per user, so a rebuild in progress never blanks the
# screen. In-memory only: a restart just costs one recompute.
_LAST_GOOD_COLLECTIONS: dict[str, list[dict]] = {}


def _features_are_stale(user_id: str) -> bool:
    item_count, max_reel_item_id = _current_reel_item_state(user_id)
    if not item_count:
        return False
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count, COALESCE(MAX(reel_item_id), 0) AS max_reel_item_id
            FROM reel_item_features
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    feature_count = int(row["count"] or 0) if row else 0
    feature_max = int(row["max_reel_item_id"] or 0) if row else 0
    return feature_count != item_count or feature_max != max_reel_item_id


def _refresh_features_if_stale(user_id: str) -> None:
    with _FEATURE_REFRESH_LOCK:
        if user_id in _FEATURE_REFRESH_IN_FLIGHT:
            return
        try:
            if not _features_are_stale(user_id):
                return
        except Exception as exc:
            print(f"[library] feature staleness check failed for {user_id}: {exc}")
            return
        _FEATURE_REFRESH_IN_FLIGHT.add(user_id)

    def run() -> None:
        try:
            PersonalizationV2Engine().backfill_user(user_id, use_llm=False, use_remote_embeddings=False)
        except Exception as exc:
            print(f"[library] feature refresh failed for {user_id}: {exc}")
        finally:
            with _FEATURE_REFRESH_LOCK:
                _FEATURE_REFRESH_IN_FLIGHT.discard(user_id)

    threading.Thread(target=run, name=f"collections-refresh-{user_id}", daemon=True).start()


def collections_status(user_id: str) -> dict:
    """Why Collections are or aren't showing for this account.

    Four things have to line up — the account is allowlisted, features exist,
    an engine published something, and the shelf survives the UI's generic
    title filter — and from the app you cannot tell which one failed. Open
    /library/status while signed in and it says which.
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT lower(email) AS email FROM users WHERE id = ? LIMIT 1", (user_id,)
        ).fetchone()
    email = (row["email"] if row else "") or ""
    is_demo = _is_demo_showcase_account(user_id)
    enabled = collections_enabled(user_id)
    item_count, _ = _current_reel_item_state(user_id)
    with get_connection() as connection:
        feature_row = connection.execute(
            "SELECT COUNT(*) AS count FROM reel_item_features WHERE user_id = ?", (user_id,)
        ).fetchone()
    feature_count = int(feature_row["count"] or 0) if feature_row else 0

    if enabled:
        reason = "demo showcase account" if is_demo else "matched COLLECTIONS_ACCOUNTS"
    elif not settings.collections_accounts:
        reason = "COLLECTIONS_ACCOUNTS is not set on this server"
    else:
        reason = (
            f"signed in as '{email or user_id}', which is not in COLLECTIONS_ACCOUNTS "
            "(it must match your account email exactly, lowercase, no spaces)"
        )

    status = {
        "user_id": user_id,
        "email": email,
        "collections_enabled": enabled,
        "reason": reason,
        "allowlist_configured": bool(settings.collections_accounts),
        "reel_items": item_count,
        "features_built": feature_count,
        "features_stale": feature_count != item_count,
        "rebuild_in_flight": user_id in _FEATURE_REFRESH_IN_FLIGHT,
        "demo_curation_applied": is_demo,
    }
    try:
        personalized = load_personalized_collections(user_id)
        status["engine"] = (
            "strong_personalization" if personalized and personalized[0].get("personalization_model")
            else ("personalization_v2" if personalized else "none")
        )
        status["shelves"] = [
            {"parent_title": c.get("parent_title", ""), "list_title": c.get("list_title", ""), "items": len(c.get("items", []))}
            for c in personalized
        ]
    except Exception as exc:
        status["engine"] = "error"
        status["error"] = repr(exc)[:300]
    return status


def load_library_payload(user_id: str) -> dict:
    collections_on = collections_enabled(user_id)
    is_demo_showcase = collections_on and _is_demo_showcase_account(user_id)
    if collections_on:
        _refresh_features_if_stale(user_id)

    if collections_on and not is_demo_showcase:
        # A rebuild wipes every feature and membership before writing them
        # back, so a request landing mid-rebuild reads half-written state and
        # gets a shelf set that is neither the old one nor the new one. The
        # engine itself is deterministic — same library in, same shelves out,
        # verified over repeated rebuilds — so every reshuffle the user sees
        # comes from reading during that window. Hold the last good answer
        # until the rebuild finishes, then switch once.
        cached = _LAST_GOOD_COLLECTIONS.get(user_id)
        with _FEATURE_REFRESH_LOCK:
            rebuilding = user_id in _FEATURE_REFRESH_IN_FLIGHT
        if rebuilding and cached:
            personalized = cached
        else:
            # Few strong shelves over the whole library, from one fixed engine.
            personalized = _curate_collections(load_personalized_collections(user_id, prefer_graph=True))
            if personalized:
                _LAST_GOOD_COLLECTIONS[user_id] = personalized
            elif cached:
                personalized = cached
        return {
            "user_id": user_id,
            "standard": [] if personalized else load_standard_collections(user_id),
            "personalized": personalized,
            "recents": load_recent_reels(user_id),
        }

    personalized = load_personalized_collections(user_id)
    if personalized and collections_on:
        # Personalization only emits the themes it could cluster confidently.
        # Whatever it left out must still reach the library as plain category
        # shelves — a thin result (one cluster on a young account) used to
        # hide every other processed reel from the collections view.
        covered = {
            item.get("reel_id")
            for collection in personalized
            for item in collection.get("items", [])
            if item.get("reel_id")
        }
        for collection in load_standard_collections(user_id):
            leftover = [item for item in collection.get("items", []) if item.get("reel_id") not in covered]
            if leftover:
                collection["items"] = leftover
                personalized.append(collection)
        personalized = _curate_demo_showcase_collections(personalized)
    standard = [] if personalized else load_standard_collections(user_id)
    return {
        "user_id": user_id,
        "standard": standard,
        "personalized": personalized,
        "recents": load_recent_reels(user_id),
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
