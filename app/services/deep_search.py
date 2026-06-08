from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import defaultdict
from typing import Any

from app.config import settings
from app.db.database import get_connection
from app.services.library import _media_url_from_path


SEARCHABLE_ATTRIBUTES = [
    "item_names",
    "product_names",
    "brands",
    "models",
    "entities",
    "locations",
    "subdomains",
    "canonical_domains",
    "primary_category",
    "secondary_category",
    "creator",
    "caption",
    "visible_text",
    "visual_entities",
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
    "entities",
    "locations",
    "visual_entities",
    "visual_summary",
    "items",
    "products",
    "media",
]

FIELD_WEIGHTS = [
    ("item_names", 120),
    ("product_names", 115),
    ("brands", 110),
    ("models", 105),
    ("entities", 95),
    ("locations", 90),
    ("subdomains", 80),
    ("canonical_domains", 70),
    ("primary_category", 65),
    ("secondary_category", 65),
    ("creator", 60),
    ("caption", 45),
    ("visible_text", 42),
    ("visual_entities", 40),
    ("product_types", 35),
    ("item_summaries", 30),
    ("transcript", 25),
    ("visual_summary", 22),
    ("visual_theme", 20),
    ("hashtags", 15),
]

SYNONYMS = {
    "coffee": ["cafe", "espresso", "latte", "cappuccino"],
    "sneakers": ["shoes", "nike", "jordan", "adidas"],
    "shoe": ["sneaker", "shoes", "footwear"],
    "shoes": ["sneaker", "sneakers", "footwear"],
    "gym": ["workout", "fitness", "training"],
    "food": ["restaurant", "recipe", "street food", "cafe"],
    "watch": ["movie", "series", "film", "show"],
    "buy": ["product", "shopping", "shop"],
    "visit": ["place", "travel", "restaurant", "cafe"],
}


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


def load_deep_search_documents(user_id: str) -> list[dict[str, Any]]:
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
        documents.append(document)

    return documents


def _tokens(query: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", query.casefold())


def _expand_query(query: str) -> tuple[list[str], list[str]]:
    primary = _tokens(query)
    expanded = []
    for token in primary:
        expanded.extend(SYNONYMS.get(token, []))
    return primary, _tokens(" ".join(expanded))


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
            for term in primary_terms:
                if term in text:
                    score += weight
                    matches.append(field)
            for term in expanded_terms:
                if term in text:
                    score += max(1, weight // 4)
                    matches.append(f"{field}:expanded")
        if score:
            scored.append((score, document, sorted(set(matches))))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [_result_payload(document, score, matches) for score, document, matches in scored[:limit]]


def _result_payload(document: dict[str, Any], score: int, matches: list[str]) -> dict[str, Any]:
    return {
        "score": score,
        "matched_fields": matches,
        "id": document["id"],
        "reel_id": document["reel_id"],
        "shortcode": document.get("shortcode", ""),
        "url": document.get("url", ""),
        "received_at": document.get("received_at", ""),
        "item_names": document.get("item_names", []),
        "product_names": document.get("product_names", []),
        "brands": document.get("brands", []),
        "entities": document.get("entities", []),
        "locations": document.get("locations", []),
        "visual_entities": document.get("visual_entities", []),
        "visual_summary": document.get("visual_summary", ""),
        "media": document.get("media", {}),
    }


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

    def configure_index(self, index_name: str) -> None:
        self.request(
            "PATCH",
            f"/indexes/{index_name}/settings",
            {
                "searchableAttributes": SEARCHABLE_ATTRIBUTES,
                "filterableAttributes": FILTERABLE_ATTRIBUTES,
                "displayedAttributes": DISPLAYED_ATTRIBUTES,
                "sortableAttributes": ["received_at"],
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
            },
        )


def index_user_documents(user_id: str, index_name: str | None = None) -> dict[str, Any]:
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
        "task": task,
    }

