from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime
from typing import Any

from app.config import settings
from app.db.database import get_connection
from app.services.library import _media_url_from_path


SEARCHABLE_ATTRIBUTES = [
    "search_terms",
    "item_names",
    "product_names",
    "brands",
    "models",
    "entities",
    "collection_titles",
    "locations",
    "parent_titles",
    "subdomains",
    "canonical_domains",
    "primary_category",
    "secondary_category",
    "creator",
    "caption",
    "visible_text",
    "visual_entities",
    "visual_supporting_points",
    "product_types",
    "item_summaries",
    "transcript",
    "visual_summary",
    "visual_theme",
    "hashtags",
]

FILTERABLE_ATTRIBUTES = [
    "user_id",
    "item_types",
    "intents",
    "canonical_domains",
    "subdomains",
    "locations",
    "brands",
    "media.media_status",
]

DISPLAYED_ATTRIBUTES = [
    "id",
    "reel_id",
    "user_id",
    "url",
    "shortcode",
    "received_at",
    "creator",
    "item_names",
    "product_names",
    "brands",
    "collection_titles",
    "parent_titles",
    "entities",
    "locations",
    "visual_entities",
    "visible_text",
    "visual_supporting_points",
    "visual_summary",
    "visual_theme",
    "match_context",
    "items",
    "products",
    "media",
]

FIELD_WEIGHTS = [
    ("item_names", 120),
    ("product_names", 115),
    ("brands", 110),
    ("models", 105),
    ("collection_titles", 100),
    ("entities", 95),
    ("locations", 90),
    ("parent_titles", 85),
    ("subdomains", 80),
    ("canonical_domains", 70),
    ("primary_category", 65),
    ("secondary_category", 65),
    ("creator", 60),
    ("caption", 45),
    ("visible_text", 42),
    ("visual_entities", 40),
    ("visual_supporting_points", 38),
    ("product_types", 35),
    ("item_summaries", 30),
    ("transcript", 25),
    ("visual_summary", 22),
    ("visual_theme", 20),
    ("hashtags", 15),
    ("search_terms", 8),
]

SYNONYMS = {
    "coffee": ["cafe", "espresso", "latte", "cappuccino"],
    "cafe": ["coffee", "espresso", "latte", "cappuccino"],
    "sneakers": ["shoes", "nike", "jordan", "adidas"],
    "shoe": ["sneaker", "shoes", "footwear"],
    "shoes": ["sneaker", "sneakers", "footwear"],
    "gym": ["workout", "fitness", "training"],
    "workout": ["gym", "fitness", "training"],
    "food": ["restaurant", "recipe", "street food", "cafe"],
    "restaurant": ["food", "cafe", "street food", "dining"],
    "restaurants": ["restaurant", "food", "cafe", "street food", "dining"],
    "watch": ["movie", "series", "film", "show"],
    "movie": ["film", "show", "series", "watch"],
    "buy": ["product", "shopping", "shop"],
    "visit": ["place", "travel", "restaurant", "cafe"],
    "bottle": ["perfume bottle", "water bottle", "fragrance bottle", "drink bottle"],
    "perfume": ["fragrance", "scent", "cologne", "attar", "perfume bottle"],
    "fragrance": ["perfume", "scent", "cologne", "attar"],
    "phone": ["mobile", "iphone", "smartphone"],
    "laptop": ["macbook", "computer", "notebook"],
    "app": ["application", "tool", "software"],
    "travel": ["trip", "destination", "place", "stay"],
    "hotel": ["stay", "villa", "airbnb", "resort"],
    "recipe": ["cook", "cooking", "food", "dish"],
    "saree": ["sari", "traditional outfit", "ethnic wear", "indian traditional wear", "dupatta"],
    "sari": ["saree", "traditional outfit", "ethnic wear", "indian traditional wear", "dupatta"],
    "traditional": ["ethnic wear", "saree", "sari", "kurta", "lehenga", "dupatta"],
    "ethnic": ["traditional outfit", "saree", "sari", "kurta", "lehenga", "dupatta"],
}

EVALUATION_QUERIES = [
    "perfume",
    "bottle",
    "nike",
    "pool",
    "book",
    "app",
    "gym",
    "cafe",
    "movie",
    "laptop",
    "travel",
    "food",
    "saree",
    "traditional outfit",
    "restaurants in Bali",
]


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _loads_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return _unique(_normalize(item) for item in value)
    if isinstance(value, tuple):
        return _unique(_normalize(item) for item in value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        parsed = _loads_json(stripped, None)
        if isinstance(parsed, list):
            return _as_list(parsed)
        return _unique(re.split(r"[;,\n|]+", stripped))
    return [_normalize(value)] if _normalize(value) else []


def _unique(values) -> list[str]:
    seen = set()
    output = []
    for value in values:
        text = _normalize(value)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


def _metadata_list(metadata: dict, *keys: str) -> list[str]:
    values = []
    for key in keys:
        values.extend(_as_list(metadata.get(key)))
    visual_backfill = metadata.get("visual_backfill")
    if isinstance(visual_backfill, dict):
        for key in keys:
            values.extend(_as_list(visual_backfill.get(key)))
    return _unique(values)


def _metadata_text(metadata: dict, *keys: str) -> str:
    for key in keys:
        text = _normalize(metadata.get(key))
        if text:
            return text
    visual_backfill = metadata.get("visual_backfill")
    if isinstance(visual_backfill, dict):
        for key in keys:
            text = _normalize(visual_backfill.get(key))
            if text:
                return text
    return ""


def _build_match_context(document: dict[str, Any]) -> str:
    parts = []
    for field in (
        "item_names",
        "product_names",
        "brands",
        "collection_titles",
        "parent_titles",
        "entities",
        "locations",
        "subdomains",
        "visible_text",
        "visual_entities",
        "visual_supporting_points",
    ):
        parts.extend(_as_list(document.get(field)))
    parts.extend(
        [
            document.get("primary_category", ""),
            document.get("secondary_category", ""),
            document.get("caption", ""),
            document.get("transcript", ""),
            document.get("visual_summary", ""),
            document.get("visual_theme", ""),
        ]
    )
    return " ".join(_unique(parts))


def _library_context_by_reel(user_id: str) -> dict[str, dict[str, list[str]]]:
    try:
        from app.services.library import load_library_payload

        payload = load_library_payload(user_id)
    except Exception:
        return {}

    context: dict[str, dict[str, list[str]]] = {}
    for section in ("personalized", "standard"):
        for collection in payload.get(section, []) or []:
            list_title = _normalize(collection.get("list_title"))
            parent_title = _normalize(collection.get("parent_title"))
            for item in collection.get("items", []) or []:
                reel_id = _normalize(item.get("reel_id"))
                if not reel_id:
                    continue
                bucket = context.setdefault(
                    reel_id,
                    {"collection_titles": [], "parent_titles": []},
                )
                bucket["collection_titles"].append(list_title)
                bucket["parent_titles"].append(parent_title)

    return {
        reel_id: {
            "collection_titles": _unique(values.get("collection_titles", [])),
            "parent_titles": _unique(values.get("parent_titles", [])),
        }
        for reel_id, values in context.items()
    }


def _build_search_terms(document: dict[str, Any]) -> list[str]:
    terms = _as_list(_build_match_context(document))
    expanded = []
    for token in _tokens(" ".join(terms)):
        expanded.extend(SYNONYMS.get(token, []))
    return _unique(terms + expanded)


def _load_persisted_deep_search_documents(user_id: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        try:
            rows = connection.execute(
                """
                SELECT document_json
                FROM deep_search_documents
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        except Exception:
            return []
    documents = []
    for row in rows:
        document = _loads_json(row["document_json"], {})
        if isinstance(document, dict) and document.get("reel_id"):
            documents.append(document)
    return documents


def load_deep_search_documents(user_id: str, prefer_persisted: bool = True) -> list[dict[str, Any]]:
    if prefer_persisted:
        persisted = _load_persisted_deep_search_documents(user_id)
        if persisted:
            return persisted
    return build_deep_search_documents_from_db(user_id)


def build_deep_search_documents_from_db(user_id: str) -> list[dict[str, Any]]:
    library_context = _library_context_by_reel(user_id)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                r.id AS reel_id,
                r.user_id AS user_id,
                r.url AS url,
                r.shortcode AS shortcode,
                r.received_at AS received_at,
                r.source AS source,
                r.media_status AS media_status,
                r.local_video_path AS local_video_path,
                r.thumbnail_path AS thumbnail_path,
                ri.id AS reel_item_id,
                ri.primary_category AS primary_category,
                ri.secondary_category AS secondary_category,
                ri.item_name AS item_name,
                ri.summary AS summary,
                COALESCE(pl.product_name, '') AS product_name,
                COALESCE(pl.brand, '') AS product_brand,
                COALESCE(pl.model, '') AS product_model,
                COALESCE(pl.product_type, '') AS product_type,
                COALESCE(pl.search_query, '') AS product_search_query,
                COALESCE(pl.best_buy_link, '') AS best_buy_link,
                COALESCE(pl.amazon_link, '') AS amazon_link,
                COALESCE(pl.flipkart_link, '') AS flipkart_link,
                COALESCE(pl.nykaa_link, '') AS nykaa_link,
                COALESCE(f.item_type, '') AS item_type,
                COALESCE(f.canonical_domain, '') AS canonical_domain,
                COALESCE(f.canonical_subdomains_json, '[]') AS canonical_subdomains_json,
                COALESCE(f.canonical_entities_json, '[]') AS canonical_entities_json,
                COALESCE(f.canonical_location, '') AS canonical_location,
                COALESCE(f.vibe_json, '[]') AS vibe_json,
                COALESCE(f.intent, '') AS intent,
                COALESCE(f.audience_context, '') AS audience_context,
                COALESCE(f.confidence_scores_json, '{}') AS confidence_scores_json,
                COALESCE(f.interpretation_source, '') AS interpretation_source,
                COALESCE(f.metadata_json, '{}') AS feature_metadata_json,
                COALESCE(d.metadata_json, '{}') AS diagnostics_metadata_json,
                COALESCE(d.caption_present, 0) AS caption_present,
                COALESCE(d.hashtags_present, 0) AS hashtags_present,
                COALESCE(d.creator_present, 0) AS creator_present,
                COALESCE(d.transcript_present, 0) AS transcript_present,
                COALESCE(d.transcript_status, '') AS transcript_status,
                COALESCE(d.visual_present, 0) AS visual_present,
                COALESCE(d.visual_status, '') AS visual_status
            FROM reels r
            LEFT JOIN reel_items ri ON ri.reel_id = r.id
            LEFT JOIN product_links pl ON pl.reel_item_id = ri.id
            LEFT JOIN reel_item_features f ON f.reel_item_id = ri.id
            LEFT JOIN reel_processing_diagnostics d ON d.reel_id = r.id
            WHERE r.user_id = ?
            ORDER BY r.received_at DESC, ri.id ASC
            """,
            (user_id,),
        ).fetchall()

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        raw = dict(row)
        grouped[raw["reel_id"]].append(raw)

    documents = []
    for reel_id, reel_rows in grouped.items():
        first = reel_rows[0]
        reel_library_context = library_context.get(reel_id, {})
        diagnostics_metadata = _loads_json(first.get("diagnostics_metadata_json"), {})
        if not isinstance(diagnostics_metadata, dict):
            diagnostics_metadata = {}

        item_names = _unique(row.get("item_name") for row in reel_rows)
        item_summaries = _unique(row.get("summary") for row in reel_rows)
        product_names = _unique(row.get("product_name") for row in reel_rows)
        brands = _unique(row.get("product_brand") for row in reel_rows)
        models = _unique(row.get("product_model") for row in reel_rows)
        product_types = _unique(row.get("product_type") for row in reel_rows)

        entities = []
        subdomains = []
        vibes = []
        locations = []
        canonical_domains = []
        intents = []
        item_types = []
        items = []
        products = []

        for row in reel_rows:
            feature_metadata = _loads_json(row.get("feature_metadata_json"), {})
            if not isinstance(feature_metadata, dict):
                feature_metadata = {}
            entities.extend(_as_list(row.get("canonical_entities_json")))
            entities.extend(_as_list(feature_metadata.get("entities")))
            subdomains.extend(_as_list(row.get("canonical_subdomains_json")))
            vibes.extend(_as_list(row.get("vibe_json")))
            locations.append(row.get("canonical_location", ""))
            canonical_domains.append(row.get("canonical_domain", ""))
            intents.append(row.get("intent", ""))
            item_types.append(row.get("item_type", ""))
            if row.get("reel_item_id"):
                items.append(
                    {
                        "reel_item_id": row.get("reel_item_id"),
                        "name": _normalize(row.get("item_name")),
                        "summary": _normalize(row.get("summary")),
                        "item_type": _normalize(row.get("item_type")),
                        "canonical_domain": _normalize(row.get("canonical_domain")),
                        "subdomains": _as_list(row.get("canonical_subdomains_json")),
                        "entities": _as_list(row.get("canonical_entities_json")),
                        "location": _normalize(row.get("canonical_location")),
                        "vibe": _as_list(row.get("vibe_json")),
                        "intent": _normalize(row.get("intent")),
                        "confidence_scores": _loads_json(row.get("confidence_scores_json"), {}),
                    }
                )
            if any(_normalize(row.get(key)) for key in ("product_name", "product_brand", "product_model", "product_type")):
                products.append(
                    {
                        "product_name": _normalize(row.get("product_name")),
                        "brand": _normalize(row.get("product_brand")),
                        "model": _normalize(row.get("product_model")),
                        "product_type": _normalize(row.get("product_type")),
                        "search_query": _normalize(row.get("product_search_query")),
                        "links": {
                            "best_buy_link": _normalize(row.get("best_buy_link")),
                            "amazon": _normalize(row.get("amazon_link")),
                            "flipkart": _normalize(row.get("flipkart_link")),
                            "nykaa": _normalize(row.get("nykaa_link")),
                        },
                    }
                )

        visible_text = _metadata_list(diagnostics_metadata, "relevant_visible_text", "visible_text", "ocr_text")
        visual_entities = _metadata_list(
            diagnostics_metadata,
            "relevant_visual_entities",
            "visual_entities",
            "objects_items",
            "places",
            "activities",
        )
        visual_supporting_points = _metadata_list(diagnostics_metadata, "visual_supporting_points")
        visual_summary = _metadata_text(
            diagnostics_metadata,
            "overall_visual_summary",
            "visual_summary",
            "scene_summary",
            "summary",
        )

        document = {
            "id": reel_id,
            "reel_id": reel_id,
            "user_id": _normalize(first.get("user_id")),
            "url": _normalize(first.get("url")),
            "shortcode": _normalize(first.get("shortcode")),
            "received_at": _normalize(first.get("received_at")),
            "source": _normalize(first.get("source")),
            "creator": _metadata_text(diagnostics_metadata, "creator"),
            "caption": _metadata_text(diagnostics_metadata, "caption"),
            "hashtags": _metadata_list(diagnostics_metadata, "hashtags"),
            "transcript": _metadata_text(diagnostics_metadata, "transcript"),
            "visible_text": visible_text,
            "visual_entities": visual_entities,
            "visual_supporting_points": visual_supporting_points,
            "visual_summary": visual_summary,
            "visual_theme": _metadata_text(diagnostics_metadata, "inferred_main_theme", "theme"),
            "primary_category": _normalize(first.get("primary_category")),
            "secondary_category": _normalize(first.get("secondary_category")),
            "item_names": item_names,
            "item_summaries": item_summaries,
            "product_names": product_names,
            "brands": brands,
            "models": models,
            "product_types": product_types,
            "collection_titles": reel_library_context.get("collection_titles", []),
            "parent_titles": reel_library_context.get("parent_titles", []),
            "entities": _unique(entities),
            "locations": _unique(locations),
            "subdomains": _unique(subdomains),
            "canonical_domains": _unique(canonical_domains),
            "vibes": _unique(vibes),
            "intents": _unique(intents),
            "item_types": _unique(item_types),
            "items": items,
            "products": products,
            "media": {
                "media_status": _normalize(first.get("media_status")),
                "thumbnail_url": _media_url_from_path(_normalize(first.get("thumbnail_path"))),
                "local_video_url": _media_url_from_path(_normalize(first.get("local_video_path"))),
            },
            "diagnostics": {
                "caption_present": bool(first.get("caption_present")),
                "hashtags_present": bool(first.get("hashtags_present")),
                "creator_present": bool(first.get("creator_present")),
                "transcript_present": bool(first.get("transcript_present")),
                "transcript_status": _normalize(first.get("transcript_status")),
                "visual_present": bool(first.get("visual_present")),
                "visual_status": _normalize(first.get("visual_status")),
            },
        }
        document["match_context"] = _build_match_context(document)
        document["search_terms"] = _build_search_terms(document)
        documents.append(document)

    return documents


def rebuild_deep_search_documents(user_id: str) -> dict[str, Any]:
    documents = build_deep_search_documents_from_db(user_id)
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as connection:
        connection.execute("DELETE FROM deep_search_documents WHERE user_id = ?", (user_id,))
        for document in documents:
            connection.execute(
                """
                INSERT INTO deep_search_documents (
                    reel_id, user_id, shortcode, url, document_json, search_terms_json,
                    source_version, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(reel_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    shortcode = excluded.shortcode,
                    url = excluded.url,
                    document_json = excluded.document_json,
                    search_terms_json = excluded.search_terms_json,
                    source_version = excluded.source_version,
                    updated_at = excluded.updated_at
                """,
                (
                    document["reel_id"],
                    document["user_id"],
                    document.get("shortcode", ""),
                    document.get("url", ""),
                    json.dumps(document, ensure_ascii=False),
                    json.dumps(document.get("search_terms", []), ensure_ascii=False),
                    "deep_search_v1",
                    now,
                    now,
                ),
            )
    return {
        "ok": True,
        "user_id": user_id,
        "document_count": len(documents),
        "updated_at": now,
    }


def _find_user_reel(user_id: str, reel_id: str = "", url: str = "", shortcode: str = "") -> dict[str, Any] | None:
    conditions = ["user_id = ?"]
    params = [user_id]
    if reel_id:
        conditions.append("id = ?")
        params.append(reel_id)
    elif url:
        conditions.append("url = ?")
        params.append(url)
    elif shortcode:
        conditions.append("shortcode = ?")
        params.append(shortcode)
    else:
        return None

    with get_connection() as connection:
        row = connection.execute(
            f"""
            SELECT id, user_id, url, shortcode, received_at, status, media_status
            FROM reels
            WHERE {' AND '.join(conditions)}
            ORDER BY received_at DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
    return dict(row) if row else None


def backfill_reel_visual_search(
    user_id: str,
    reel_id: str = "",
    url: str = "",
    shortcode: str = "",
) -> dict[str, Any]:
    reel = _find_user_reel(user_id, reel_id=reel_id.strip(), url=url.strip(), shortcode=shortcode.strip())
    if not reel:
        return {
            "ok": False,
            "error": "reel_not_found",
            "user_id": user_id,
            "reel_id": reel_id,
            "url": url,
            "shortcode": shortcode,
        }

    with get_connection() as connection:
        row = connection.execute(
            "SELECT metadata_json FROM reel_processing_diagnostics WHERE reel_id = ? LIMIT 1",
            (reel["id"],),
        ).fetchone()
    metadata = _loads_json(row["metadata_json"], {}) if row else {}
    if not isinstance(metadata, dict):
        metadata = {}

    from data_preprocessing import download_reel
    from finale import extract_visual_data
    from app.services.reel_ingest import upsert_reel_processing_diagnostics

    video_path, video_status = download_reel(reel["url"])
    if not video_path:
        return {
            "ok": False,
            "error": "video_download_failed",
            "user_id": user_id,
            "reel_id": reel["id"],
            "url": reel["url"],
            "video_download_status": video_status,
        }

    visual_data = extract_visual_data(
        {
            "caption": _metadata_text(metadata, "caption"),
            "transcript": _metadata_text(metadata, "transcript"),
            "hashtags": _metadata_list(metadata, "hashtags"),
            "creator": _metadata_text(metadata, "creator"),
        },
        video_path,
    )
    merged_metadata = {
        **metadata,
        "inferred_main_theme": visual_data.get("inferred_main_theme", ""),
        "relevant_visible_text": visual_data.get("relevant_visible_text", []),
        "relevant_visual_entities": visual_data.get("relevant_visual_entities", []),
        "visual_supporting_points": visual_data.get("visual_supporting_points", []),
        "overall_visual_summary": visual_data.get("overall_visual_summary", ""),
        "visual_backfill": visual_data,
    }
    upsert_reel_processing_diagnostics(
        reel["url"],
        {
            "visual_present": bool(visual_data),
            "visual_status": "success" if visual_data else "empty",
            "video_download_status": video_status,
            "processing_version": "deep_search_visual_backfill_v1",
            "metadata": merged_metadata,
        },
    )
    rebuild = rebuild_deep_search_documents(user_id)
    indexed_task = None
    index_error = ""
    if settings.meili_host:
        try:
            indexed_task = index_user_documents(user_id)
        except Exception as exc:
            index_error = str(exc)
    return {
        "ok": True,
        "user_id": user_id,
        "reel_id": reel["id"],
        "url": reel["url"],
        "shortcode": reel.get("shortcode", ""),
        "video_download_status": video_status,
        "visual_data": visual_data,
        "rebuild": rebuild,
        "indexed_task": indexed_task,
        "index_error": index_error,
    }


def _tokens(query: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", query.casefold())


def _expand_query(query: str) -> tuple[list[str], list[str]]:
    primary = _tokens(query)
    expanded = []
    for token in primary:
        expanded.extend(SYNONYMS.get(token, []))
    return primary, _tokens(" ".join(expanded))


def expanded_query_text(query: str) -> str:
    primary_terms, expanded_terms = _expand_query(query)
    terms = _unique(primary_terms + expanded_terms)
    return " ".join(terms) or query


def _field_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.casefold()
    if isinstance(value, list):
        return " ".join(_field_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_field_text(item) for item in value.values())
    return str(value).casefold()


def _contains_term(text: str, term: str) -> bool:
    if not term:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


def search_documents_locally(documents: list[dict[str, Any]], query: str, limit: int = 20) -> list[dict[str, Any]]:
    primary_terms, expanded_terms = _expand_query(query)
    scored = []
    for document in documents:
        score = 0
        matches = []
        for field, weight in FIELD_WEIGHTS:
            text = _field_text(document.get(field))
            if not text:
                continue
            phrase = query.casefold().strip()
            if phrase and len(phrase) >= 3 and phrase in text:
                score += weight * 2
                matches.append(field)
            for term in primary_terms:
                if _contains_term(text, term):
                    score += weight
                    matches.append(field)
            for term in expanded_terms:
                if _contains_term(text, term):
                    score += max(1, weight // 4)
                    matches.append(f"{field}:expanded")
        if score:
            score += _freshness_boost(document.get("received_at", ""))
            scored.append((score, document, sorted(set(matches))))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [_result_payload(document, score, matches) for score, document, matches in scored[:limit]]


def _freshness_boost(received_at: str) -> int:
    match = re.search(r"(20\d{2})", received_at or "")
    if not match:
        return 0
    year = int(match.group(1))
    return max(0, min(25, year - 2020))


def _match_reasons(document: dict[str, Any], matches: list[str]) -> list[str]:
    fields = {str(field).split(":")[0] for field in matches}
    reasons = []

    def add(label: str, values: Any, limit: int = 3) -> None:
        items = _as_list(values)[:limit]
        if items:
            reasons.append(f"{label}: {', '.join(items)}")

    if fields & {"visual_entities", "visual_summary", "visual_theme", "visible_text", "visual_supporting_points"}:
        add("Seen", document.get("visual_entities"))
        add("On-screen text", document.get("visible_text"))
        add("Visual clue", document.get("visual_supporting_points"), limit=2)
        if document.get("visual_summary"):
            reasons.append(f"Visual summary: {_normalize(document.get('visual_summary'))}")
    if fields & {"product_names", "brands", "models", "product_types"}:
        add("Product", document.get("product_names"))
        add("Brand", document.get("brands"))
    if fields & {"collection_titles", "parent_titles"}:
        add("Folder", document.get("collection_titles"))
        add("Group", document.get("parent_titles"), limit=2)
    if fields & {"entities", "item_names"}:
        add("Item", document.get("item_names") or document.get("entities"))
    if fields & {"locations"}:
        add("Place", document.get("locations"))
    if fields & {"caption", "transcript", "hashtags"}:
        reasons.append("Matched caption, transcript, or hashtags")
    if fields & {"primary_category", "secondary_category", "subdomains", "canonical_domains", "intents"}:
        add("Category", [document.get("primary_category"), document.get("secondary_category")])

    return _unique(reasons)[:4]


def _result_payload(document: dict[str, Any], score: int, matches: list[str]) -> dict[str, Any]:
    return {
        "score": score,
        "matched_fields": matches,
        "match_reasons": _match_reasons(document, matches),
        "id": document["id"],
        "reel_id": document["reel_id"],
        "shortcode": document.get("shortcode", ""),
        "url": document.get("url", ""),
        "received_at": document.get("received_at", ""),
        "item_names": document.get("item_names", []),
        "product_names": document.get("product_names", []),
        "brands": document.get("brands", []),
        "collection_titles": document.get("collection_titles", []),
        "parent_titles": document.get("parent_titles", []),
        "entities": document.get("entities", []),
        "locations": document.get("locations", []),
        "visual_entities": document.get("visual_entities", []),
        "visible_text": document.get("visible_text", []),
        "visual_supporting_points": document.get("visual_supporting_points", []),
        "visual_summary": document.get("visual_summary", ""),
        "visual_theme": document.get("visual_theme", ""),
        "match_context": document.get("match_context", ""),
        "media": document.get("media", {}),
    }


def _meili_hit_payload(hit: dict[str, Any], rank: int) -> dict[str, Any]:
    matches = list(hit.get("_formatted", {}).keys()) if isinstance(hit.get("_formatted"), dict) else []
    return {
        "score": max(1, 1000 - rank),
        "matched_fields": matches,
        "match_reasons": _match_reasons(hit, matches),
        "id": hit.get("id", ""),
        "reel_id": hit.get("reel_id", ""),
        "shortcode": hit.get("shortcode", ""),
        "url": hit.get("url", ""),
        "received_at": hit.get("received_at", ""),
        "item_names": hit.get("item_names", []),
        "product_names": hit.get("product_names", []),
        "brands": hit.get("brands", []),
        "collection_titles": hit.get("collection_titles", []),
        "parent_titles": hit.get("parent_titles", []),
        "entities": hit.get("entities", []),
        "locations": hit.get("locations", []),
        "visual_entities": hit.get("visual_entities", []),
        "visible_text": hit.get("visible_text", []),
        "visual_supporting_points": hit.get("visual_supporting_points", []),
        "visual_summary": hit.get("visual_summary", ""),
        "visual_theme": hit.get("visual_theme", ""),
        "match_context": hit.get("match_context", ""),
        "media": hit.get("media", {}),
    }


def meili_synonyms() -> dict[str, list[str]]:
    synonyms: dict[str, list[str]] = {}
    for term, related in SYNONYMS.items():
        group = _unique([term] + related)
        for item in group:
            synonyms[item] = _unique(value for value in group if value.casefold() != item.casefold())
    return synonyms


class MeiliClient:
    def __init__(self, host: str | None = None, api_key: str | None = None) -> None:
        self.host = (host or settings.meili_host).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.meili_master_key

    def enabled(self) -> bool:
        return bool(self.host)

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        if not self.enabled():
            raise RuntimeError("Meilisearch is not configured. Set MEILI_HOST first.")
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.host}{path}",
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            raise RuntimeError(f"Meilisearch {method} {path} failed: {exc.code} {body}") from exc
        return json.loads(body) if body else None

    def ensure_index(self, index_name: str) -> None:
        try:
            self.request("POST", "/indexes", {"uid": index_name, "primaryKey": "id"})
        except RuntimeError as exc:
            message = str(exc).lower()
            if "already exists" not in message and "index_already_exists" not in message:
                raise

    def configure_index(self, index_name: str) -> None:
        self.ensure_index(index_name)
        self.request(
            "PATCH",
            f"/indexes/{index_name}/settings",
            {
                "searchableAttributes": SEARCHABLE_ATTRIBUTES,
                "filterableAttributes": FILTERABLE_ATTRIBUTES,
                "displayedAttributes": DISPLAYED_ATTRIBUTES,
                "sortableAttributes": ["received_at"],
                "synonyms": meili_synonyms(),
                "typoTolerance": {
                    "enabled": True,
                    "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 8},
                },
                "rankingRules": ["words", "typo", "proximity", "attribute", "sort", "exactness"],
            },
        )

    def add_documents(self, index_name: str, documents: list[dict[str, Any]]) -> Any:
        return self.request("POST", f"/indexes/{index_name}/documents?primaryKey=id", documents)

    def search(self, index_name: str, query: str, user_id: str, limit: int = 20) -> Any:
        return self.request(
            "POST",
            f"/indexes/{index_name}/search",
            {
                "q": query,
                "limit": limit,
                "filter": f'user_id = "{user_id}"',
                "attributesToHighlight": [
                    "item_names",
                    "product_names",
                    "brands",
                    "collection_titles",
                    "parent_titles",
                    "entities",
                    "visual_entities",
                    "visible_text",
                    "visual_supporting_points",
                    "visual_summary",
                    "visual_theme",
                ],
                "highlightPreTag": "<mark>",
                "highlightPostTag": "</mark>",
            },
        )


def index_user_documents(user_id: str, index_name: str | None = None) -> dict[str, Any]:
    rebuild = rebuild_deep_search_documents(user_id)
    documents = load_deep_search_documents(user_id)
    client = MeiliClient()
    target_index = index_name or settings.meili_index
    client.configure_index(target_index)
    task = client.add_documents(target_index, documents)
    return {
        "ok": True,
        "user_id": user_id,
        "index": target_index,
        "document_count": len(documents),
        "rebuild": rebuild,
        "task": task,
    }


def search_user_documents(user_id: str, query: str, limit: int = 20, backend: str = "auto") -> dict[str, Any]:
    documents = load_deep_search_documents(user_id)
    local_results = search_documents_locally(documents, query, limit=limit)
    rebuilt_for_empty_results = None
    if not local_results and documents:
        rebuilt_for_empty_results = rebuild_deep_search_documents(user_id)
        documents = load_deep_search_documents(user_id)
        local_results = search_documents_locally(documents, query, limit=limit)

    if backend == "local" or not settings.meili_host:
        return {
            "user_id": user_id,
            "query": query,
            "backend": "local",
            "document_count": len(documents),
            "rebuilt_for_empty_results": rebuilt_for_empty_results,
            "results": local_results,
        }

    client = MeiliClient()
    meili_error = ""
    indexed_task = None
    try:
        meili_result = client.search(settings.meili_index, query, user_id=user_id, limit=limit)
        hits = meili_result.get("hits", []) if isinstance(meili_result, dict) else []
        if not hits and expanded_query_text(query) != query:
            meili_result = client.search(settings.meili_index, expanded_query_text(query), user_id=user_id, limit=limit)
            hits = meili_result.get("hits", []) if isinstance(meili_result, dict) else []
        if hits:
            meili_results = [_meili_hit_payload(hit, rank) for rank, hit in enumerate(hits)]
            return {
                "user_id": user_id,
                "query": query,
                "backend": "hybrid",
                "index": settings.meili_index,
                "document_count": len(documents),
                "results": _merge_results(local_results, meili_results, limit),
                "raw_hit_count": len(hits),
                "rebuilt_for_empty_results": rebuilt_for_empty_results,
            }
        if documents and backend == "auto":
            client.configure_index(settings.meili_index)
            indexed_task = client.add_documents(settings.meili_index, documents)
    except Exception as exc:
        meili_error = str(exc)
        if backend == "meili":
            raise
        if documents and backend == "auto":
            try:
                client.configure_index(settings.meili_index)
                indexed_task = client.add_documents(settings.meili_index, documents)
            except Exception as seed_exc:
                meili_error = f"{meili_error}; seed failed: {seed_exc}"

    return {
        "user_id": user_id,
        "query": query,
        "backend": "local_fallback",
        "index": settings.meili_index if settings.meili_host else "",
        "document_count": len(documents),
        "results": local_results,
        "meili_error": meili_error,
        "indexed_task": indexed_task,
        "rebuilt_for_empty_results": rebuilt_for_empty_results,
    }


def _merge_results(primary: list[dict[str, Any]], secondary: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    merged = []
    seen = set()
    for result in primary + secondary:
        key = result.get("reel_id") or result.get("id") or result.get("url")
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(result)
        if len(merged) >= limit:
            break
    return merged


def explain_user_search(user_id: str, query: str, limit: int = 10) -> dict[str, Any]:
    documents = load_deep_search_documents(user_id)
    if not query:
        return {
            "user_id": user_id,
            "query": query,
            "query_terms": [],
            "expanded_terms": [],
            "document_count": len(documents),
            "backend": "none",
            "results": [],
        }
    payload = search_user_documents(user_id, query, limit=limit, backend="auto")
    terms, expanded = _expand_query(query)
    return {
        "user_id": user_id,
        "query": query,
        "query_terms": terms,
        "expanded_terms": _unique(expanded),
        "document_count": len(documents),
        "backend": payload.get("backend"),
        "meili_error": payload.get("meili_error", ""),
        "results": [
            {
                "rank": index + 1,
                "reel_id": result.get("reel_id"),
                "shortcode": result.get("shortcode"),
                "url": result.get("url"),
                "score": result.get("score"),
                "matched_fields": result.get("matched_fields", []),
                "match_reasons": result.get("match_reasons", []),
                "item_names": result.get("item_names", []),
                "visual_entities": result.get("visual_entities", []),
                "visible_text": result.get("visible_text", []),
                "visual_supporting_points": result.get("visual_supporting_points", []),
                "visual_summary": result.get("visual_summary", ""),
                "collection_titles": result.get("collection_titles", []),
                "parent_titles": result.get("parent_titles", []),
            }
            for index, result in enumerate(payload.get("results", [])[:limit])
        ],
    }


def evaluate_user_search(user_id: str, queries: list[str] | None = None, limit: int = 5) -> dict[str, Any]:
    query_list = queries or EVALUATION_QUERIES
    rows = []
    for query in query_list:
        payload = search_user_documents(user_id, query, limit=limit, backend="auto")
        rows.append(
            {
                "query": query,
                "backend": payload.get("backend", ""),
                "result_count": len(payload.get("results", [])),
                "top_results": payload.get("results", [])[:limit],
            }
        )
    return {
        "user_id": user_id,
        "queries": query_list,
        "limit": limit,
        "rows": rows,
    }
