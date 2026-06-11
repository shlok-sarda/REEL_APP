from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "app.db"
DEFAULT_OUTPUT_DIR = BASE_DIR / "outputs" / "strong_personalization"

MIN_ITEMS_TO_PUBLISH = 5
MIN_AVG_PAIRWISE_SIMILARITY = 0.62
MIN_PAIRWISE_SIMILARITY = 0.50
MIN_LOCATION_FOOD_PAIRWISE_SIMILARITY = 0.42
MIN_PURITY = 0.85
MIN_MEMBER_SCORE = 0.72
RECALL_MEMBER_SCORE = 0.70

FOOD_PLACE_LABELS = {
    "restaurant",
    "restaurants",
    "seafood restaurants",
    "street food",
    "cafes",
    "late-night food",
    "local food",
    "dessert spots",
}

TRAVEL_FOOD_DOMAINS = {
    "Travel & Food",
    "Food & Local Eats",
    "Food & Dining",
    "Travel Destinations",
    "Travel Accommodations",
    "Travel",
}

TITLE_OVERRIDES = {
    "app": "Apps & Tools",
    "learning app": "Apps & Tools",
    "job search tools": "Apps & Tools",
    "ai": "AI Tools",
    "device": "Gadgets & Devices",
    "audio device": "Gadgets & Devices",
    "kitchen device": "Gadgets & Devices",
    "consumer tech": "Gadgets & Devices",
    "fitness accessories": "Gadgets & Devices",
    "fragrance": "Fragrances",
    "home products": "Home Products",
    "slides and sandals": "Slides & Sandals",
    "sneaker culture": "Sneakers",
    "films and shows": "Films & Shows",
    "music": "Music",
    "recipes": "Recipes",
    "protein recipes": "Recipes",
    "fitness": "Fitness",
    "wellness": "Wellness",
    "motivation and mindset": "Motivation & Mindset",
    "wealth education": "Career & Money",
    "startup advice": "Career & Money",
    "money making ideas": "Career & Money",
}


def normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def key(value: Any) -> str:
    return normalize(value).lower()


def load_json(value: str, fallback: Any) -> Any:
    if not normalize(value):
        return fallback
    try:
        parsed = json.loads(value)
    except Exception:
        return fallback
    return parsed if parsed is not None else fallback


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize(item) for item in value if normalize(item)]
    if isinstance(value, str) and value.strip().startswith("["):
        return as_list(load_json(value, []))
    if normalize(value):
        return [normalize(value)]
    return []


def tokens(*parts: str) -> set[str]:
    text = " ".join(normalize(part).lower() for part in parts if normalize(part))
    return {tok for tok in re.findall(r"[a-z0-9]+", text) if len(tok) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / max(len(a | b), 1)


def food_place_text_signal(item: "Item") -> bool:
    food_text = key(" ".join([item.specific_category, item.item_name, item.summary]))
    return bool(
        re.search(
            r"\b(?:restaurant|restaurants|cafe|cafes|street food|food spot|food spots|eatery|eateries|"
            r"bhel|laphing|momos|kebab|paratha|dimsum|doughnut|dessert|chaat|chicken fry|non-veg|seafood)\b",
            food_text,
        )
    )


def effective_labels(item: "Item") -> set[str]:
    labels = set(item.lower_subdomains)
    if item.location and item.item_type == "place" and item.intent == "place_to_visit" and food_place_text_signal(item):
        labels.add("restaurants")
    return labels


@dataclass
class Item:
    reel_item_id: int
    reel_id: str
    user_id: str
    url: str
    received_at: str
    primary_category: str
    specific_category: str
    item_name: str
    summary: str
    product_name: str
    brand: str
    model: str
    product_type: str
    search_query: str
    item_type: str
    canonical_domain: str
    subdomains: list[str]
    entities: list[str]
    location: str
    vibe: list[str]
    intent: str
    confidence_scores: dict[str, float]
    text_tokens: set[str] = field(default_factory=set)

    @property
    def lower_subdomains(self) -> set[str]:
        return {key(value) for value in self.subdomains}

    @property
    def lower_entities(self) -> set[str]:
        return {key(value) for value in self.entities if key(value)}

    @property
    def primary_label(self) -> str:
        labels = [key(value) for value in self.subdomains if key(value)]
        for preferred in [
            "seafood restaurants",
            "street food",
            "restaurants",
            "restaurant",
            "cafes",
            "late-night food",
            "stay",
            "destinations",
            "fragrance",
            "home products",
            "slides and sandals",
            "sneaker culture",
            "films and shows",
            "music",
            "app",
            "job search tools",
            "ai",
            "device",
            "audio device",
            "kitchen device",
            "consumer tech",
            "protein recipes",
            "recipes",
            "fitness",
            "motivation and mindset",
        ]:
            if preferred in labels:
                return preferred
        return labels[0] if labels else ""


@dataclass
class CandidateDefinition:
    candidate_key: str
    title: str
    family: str
    canonical_domain: str
    location: str = ""
    allowed_labels: set[str] = field(default_factory=set)
    allowed_domains: set[str] = field(default_factory=set)
    allowed_item_types: set[str] = field(default_factory=set)
    allowed_intents: set[str] = field(default_factory=set)
    required_location: bool = False


def load_items(db_path: Path, user_id: str) -> list[Item]:
    query = """
        SELECT
            ri.id AS reel_item_id,
            ri.reel_id,
            r.user_id,
            r.url,
            r.received_at,
            ri.primary_category,
            ri.secondary_category AS specific_category,
            ri.item_name,
            ri.summary,
            COALESCE(pl.product_name, '') AS product_name,
            COALESCE(pl.brand, '') AS brand,
            COALESCE(pl.model, '') AS model,
            COALESCE(pl.product_type, '') AS product_type,
            COALESCE(pl.search_query, '') AS search_query,
            rif.item_type,
            rif.canonical_domain,
            rif.canonical_subdomains_json,
            rif.canonical_entities_json,
            rif.canonical_location,
            rif.vibe_json,
            rif.intent,
            rif.confidence_scores_json
        FROM reel_items ri
        JOIN reels r ON r.id = ri.reel_id
        JOIN reel_item_features rif ON rif.reel_item_id = ri.id
        LEFT JOIN product_links pl ON pl.reel_item_id = ri.id
        WHERE r.user_id = ?
        ORDER BY r.received_at ASC, ri.id ASC
    """
    rows: list[Item] = []
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        for row in connection.execute(query, (user_id,)).fetchall():
            subdomains = as_list(load_json(row["canonical_subdomains_json"], []))
            entities = as_list(load_json(row["canonical_entities_json"], []))
            confidence = load_json(row["confidence_scores_json"], {})
            item = Item(
                reel_item_id=int(row["reel_item_id"]),
                reel_id=normalize(row["reel_id"]),
                user_id=normalize(row["user_id"]),
                url=normalize(row["url"]),
                received_at=normalize(row["received_at"]),
                primary_category=normalize(row["primary_category"]),
                specific_category=normalize(row["specific_category"]),
                item_name=normalize(row["item_name"]),
                summary=normalize(row["summary"]),
                product_name=normalize(row["product_name"]),
                brand=normalize(row["brand"]),
                model=normalize(row["model"]),
                product_type=normalize(row["product_type"]),
                search_query=normalize(row["search_query"]),
                item_type=key(row["item_type"]),
                canonical_domain=normalize(row["canonical_domain"]) or "Miscellaneous",
                subdomains=subdomains,
                entities=entities,
                location=normalize(row["canonical_location"]),
                vibe=as_list(load_json(row["vibe_json"], [])),
                intent=key(row["intent"]),
                confidence_scores={k: float(v) for k, v in confidence.items() if isinstance(v, (int, float))},
            )
            item.text_tokens = tokens(
                item.primary_category,
                item.specific_category,
                item.item_name,
                item.summary,
                item.product_name,
                item.brand,
                item.product_type,
                " ".join(item.subdomains),
                " ".join(item.entities),
                item.location,
            )
            rows.append(item)
    return rows


def definition_for_item(item: Item) -> CandidateDefinition | None:
    label = item.primary_label
    labels = item.lower_subdomains
    domain = item.canonical_domain
    domain_key = key(domain)

    if item.location and (
        item.item_type == "place"
        or labels & FOOD_PLACE_LABELS
        or domain in TRAVEL_FOOD_DOMAINS
    ):
        if labels & FOOD_PLACE_LABELS or domain in {"Food & Local Eats", "Food & Dining"}:
            return CandidateDefinition(
                candidate_key=f"food_places::{key(item.location)}",
                title=f"Restaurants in {item.location}",
                family="food_places",
                canonical_domain="Food & Local Eats" if domain.startswith("Food") else domain,
                location=item.location,
                allowed_labels=set(FOOD_PLACE_LABELS),
                allowed_domains=set(TRAVEL_FOOD_DOMAINS),
                allowed_item_types={"place"},
                allowed_intents={"place_to_visit", "general_reference"},
                required_location=True,
            )
        if label in {"stay", "local rentals"}:
            return CandidateDefinition(
                candidate_key=f"stays::{key(item.location)}",
                title=f"{item.location} Stay",
                family="stays",
                canonical_domain=domain,
                location=item.location,
                allowed_labels={"stay", "local rentals"},
                allowed_domains=set(TRAVEL_FOOD_DOMAINS) | {"Local Info"},
                allowed_item_types={"place", "general"},
                allowed_intents={"place_to_visit", "general_reference"},
                required_location=True,
            )
        if label in {"destinations", "travel planning", "cultural experience"}:
            return CandidateDefinition(
                candidate_key=f"destination::{key(item.location)}",
                title=item.location,
                family="destination",
                canonical_domain=domain,
                location=item.location,
                allowed_labels={"destinations", "travel planning", "cultural experience"},
                allowed_domains=set(TRAVEL_FOOD_DOMAINS),
                allowed_item_types={"place", "idea", "general"},
                allowed_intents={"place_to_visit", "idea_to_try", "general_reference"},
                required_location=True,
            )

    if labels & {"fragrance"}:
        return simple_definition("fragrance", "Fragrances", "Lifestyle", {"fragrance"}, {"product"}, {"product_to_buy"})
    if labels & {"home products"}:
        return simple_definition("home_products", "Home Products", "Lifestyle", {"home products"}, {"product"}, {"product_to_buy"})
    if labels & {"slides and sandals"}:
        return simple_definition("slides_sandals", "Slides & Sandals", "Lifestyle", {"slides and sandals"}, {"product"}, {"product_to_buy"})
    if labels & {"sneaker culture"}:
        return simple_definition("sneakers", "Sneakers", "Lifestyle", {"sneaker culture"}, {"product"}, {"product_to_buy"})
    if labels & {"films and shows"}:
        return simple_definition("films_shows", "Films & Shows", "Entertainment", {"films and shows"}, {"media"}, {"media_to_watch_or_hear"})
    if labels & {"music"}:
        return simple_definition("music", "Music", "Entertainment", {"music"}, {"media"}, {"media_to_watch_or_hear"})
    if labels & {"app", "learning app", "job search tools"} or item.item_type == "app":
        return simple_definition("apps_tools", "Apps & Tools", "Technology", {"app", "learning app", "job search tools", "ai"}, {"app"}, {"tool_to_use"})
    if labels & {"device", "audio device", "kitchen device", "consumer tech", "fitness accessories"}:
        return simple_definition(
            "gadgets_devices",
            "Gadgets & Devices",
            "Technology",
            {"device", "audio device", "kitchen device", "consumer tech", "fitness accessories"},
            {"product"},
            {"product_to_buy", "tool_to_use"},
        )
    if labels & {"recipes", "protein recipes"} or item.item_type == "recipe":
        return simple_definition("recipes", "Recipes", "Food & Recipes", {"recipes", "protein recipes"}, {"recipe"}, {"recipe_to_make"})
    if labels & {"fitness", "wellness"}:
        return simple_definition("fitness_wellness", "Fitness & Wellness", "Fitness & Health", {"fitness", "wellness"}, {"idea", "general"}, {"idea_to_try", "advice_to_remember"})
    if labels & {"motivation and mindset"}:
        return simple_definition("motivation_mindset", "Motivation & Mindset", "Personal Growth", {"motivation and mindset"}, {"idea"}, {"advice_to_remember", "idea_to_try"})
    if domain_key in {"generic", "miscellaneous"} or label in {"", "general"}:
        return None
    return None


def simple_definition(
    candidate_key: str,
    title: str,
    domain: str,
    labels: set[str],
    item_types: set[str],
    intents: set[str],
) -> CandidateDefinition:
    return CandidateDefinition(
        candidate_key=candidate_key,
        title=title,
        family=candidate_key,
        canonical_domain=domain,
        allowed_labels=set(labels),
        allowed_domains={domain, "Health & Lifestyle", "Lifestyle"} if domain == "Lifestyle" else {domain},
        allowed_item_types=set(item_types),
        allowed_intents=set(intents),
    )


def membership_score(item: Item, definition: CandidateDefinition) -> tuple[float, dict[str, float]]:
    label_overlap = 1.0 if item.lower_subdomains & definition.allowed_labels else 0.0
    has_food_place_text_signal = False
    if definition.family == "food_places":
        has_food_place_text_signal = food_place_text_signal(item)
    if definition.family == "food_places" and (item.lower_subdomains & FOOD_PLACE_LABELS or has_food_place_text_signal):
        label_overlap = 1.0
    domain_score = 1.0 if item.canonical_domain in definition.allowed_domains else 0.0
    location_score = 1.0 if definition.location and key(item.location) == key(definition.location) else 0.0
    if not definition.required_location:
        location_score = 1.0
    item_type_score = 1.0 if not definition.allowed_item_types or item.item_type in definition.allowed_item_types else 0.0
    intent_score = 1.0 if not definition.allowed_intents or item.intent in definition.allowed_intents else 0.0

    if definition.required_location and location_score <= 0:
        score = 0.0
    elif definition.family == "food_places":
        score = (
            0.34 * location_score
            + 0.34 * label_overlap
            + 0.12 * domain_score
            + 0.10 * item_type_score
            + 0.10 * intent_score
        )
    else:
        score = (
            0.42 * label_overlap
            + 0.20 * domain_score
            + 0.14 * item_type_score
            + 0.14 * intent_score
            + 0.10 * location_score
        )
    reasons = {
        "label": round(label_overlap, 3),
        "domain": round(domain_score, 3),
        "location": round(location_score, 3),
        "item_type": round(item_type_score, 3),
        "intent": round(intent_score, 3),
    }
    return round(score, 4), reasons


def pairwise_similarity(a: Item, b: Item) -> float:
    domain = 1.0 if a.canonical_domain == b.canonical_domain else 0.0
    location = 1.0 if a.location and a.location == b.location else (0.35 if not a.location and not b.location else 0.0)
    labels = jaccard(effective_labels(a), effective_labels(b))
    intent = 1.0 if a.intent and a.intent == b.intent else 0.0
    item_type = 1.0 if a.item_type and a.item_type == b.item_type else 0.0
    entity = jaccard(a.lower_entities, b.lower_entities)
    lexical = jaccard(a.text_tokens, b.text_tokens)
    return round(
        0.18 * domain
        + 0.18 * location
        + 0.27 * labels
        + 0.14 * intent
        + 0.11 * item_type
        + 0.04 * entity
        + 0.08 * lexical,
        4,
    )


def candidate_metrics(items: list[Item], definition: CandidateDefinition) -> dict[str, Any]:
    member_scores = [membership_score(item, definition)[0] for item in items]
    purity = sum(1 for score in member_scores if score >= MIN_MEMBER_SCORE) / max(len(items), 1)
    pairs = []
    for index, left in enumerate(items):
        for right in items[index + 1:]:
            pairs.append(pairwise_similarity(left, right))
    return {
        "item_count": len(items),
        "avg_pairwise_similarity": round(sum(pairs) / len(pairs), 4) if pairs else 1.0,
        "min_pairwise_similarity": round(min(pairs), 4) if pairs else 1.0,
        "purity": round(purity, 4),
        "avg_member_score": round(sum(member_scores) / max(len(member_scores), 1), 4),
        "min_member_score": round(min(member_scores), 4) if member_scores else 0.0,
    }


def min_pairwise_threshold_for_definition(definition: CandidateDefinition | None) -> float:
    if definition and definition.family == "food_places" and definition.required_location:
        return MIN_LOCATION_FOOD_PAIRWISE_SIMILARITY
    return MIN_PAIRWISE_SIMILARITY


def should_publish(
    metrics: dict[str, Any],
    enforce_min_pairwise: bool = True,
    definition: CandidateDefinition | None = None,
) -> tuple[bool, list[str]]:
    failures = []
    if metrics["item_count"] < MIN_ITEMS_TO_PUBLISH:
        failures.append(f"item_count<{MIN_ITEMS_TO_PUBLISH}")
    if metrics["avg_pairwise_similarity"] < MIN_AVG_PAIRWISE_SIMILARITY:
        failures.append(f"avg_pairwise_similarity<{MIN_AVG_PAIRWISE_SIMILARITY}")
    min_pairwise_threshold = min_pairwise_threshold_for_definition(definition)
    if enforce_min_pairwise and metrics["min_pairwise_similarity"] < min_pairwise_threshold:
        failures.append(f"min_pairwise_similarity<{min_pairwise_threshold}")
    if metrics["purity"] < MIN_PURITY:
        failures.append(f"purity<{MIN_PURITY}")
    if metrics["avg_member_score"] < MIN_MEMBER_SCORE:
        failures.append(f"avg_member_score<{MIN_MEMBER_SCORE}")
    return not failures, failures


def item_payload(item: Item, score: float | None = None, reasons: dict[str, float] | None = None) -> dict[str, Any]:
    payload = {
        "reel_item_id": item.reel_item_id,
        "reel_id": item.reel_id,
        "url": item.url,
        "item_name": item.item_name,
        "summary": item.summary,
        "primary_category": item.primary_category,
        "specific_category": item.specific_category,
        "item_type": item.item_type,
        "canonical_domain": item.canonical_domain,
        "subdomains": item.subdomains,
        "entities": item.entities,
        "location": item.location,
        "intent": item.intent,
        "product_name": item.product_name,
        "brand": item.brand,
    }
    if score is not None:
        payload["membership_score"] = score
    if reasons:
        payload["membership_reasons"] = reasons
    return payload


def best_definition_match(
    item: Item,
    definitions: list[CandidateDefinition],
) -> tuple[CandidateDefinition | None, float, dict[str, float]]:
    best_definition = None
    best_score = 0.0
    best_reasons: dict[str, float] = {}
    for definition in definitions:
        score, reasons = membership_score(item, definition)
        if score > best_score:
            best_definition = definition
            best_score = score
            best_reasons = reasons
    return best_definition, round(best_score, 4), best_reasons


def build_item_audit(
    items: list[Item],
    published_lists: list[dict[str, Any]],
    hidden_candidates: list[dict[str, Any]],
    rejected_after_recall: list[dict[str, Any]],
    seed_groups: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    published_definitions = [
        CandidateDefinition(
            candidate_key=collection["candidate_key"],
            title=collection["title"],
            family=collection["definition"].get("family", ""),
            canonical_domain=collection["definition"].get("canonical_domain", ""),
            location=collection["definition"].get("location", ""),
            allowed_labels=set(collection["definition"].get("allowed_labels", [])),
            allowed_domains=set(collection["definition"].get("allowed_domains", [])),
            allowed_item_types=set(collection["definition"].get("allowed_item_types", [])),
            allowed_intents=set(collection["definition"].get("allowed_intents", [])),
            required_location=bool(collection["definition"].get("required_location")),
        )
        for collection in published_lists
    ]
    seed_definitions = [group["definition"] for group in seed_groups.values()]
    hidden_by_key = {row["candidate_key"]: row for row in hidden_candidates}
    rejected_by_key = {row["candidate_key"]: row for row in rejected_after_recall}
    published_by_key = {row["candidate_key"]: row for row in published_lists}
    assignment_by_item_id: dict[int, dict[str, Any]] = {}
    for collection in published_lists:
        for item in collection["items"]:
            assignment_by_item_id[int(item["reel_item_id"])] = {
                "list_title": collection["title"],
                "membership_score": item.get("membership_score", ""),
                "membership_reasons": item.get("membership_reasons", {}),
            }

    audit_rows = []
    for item in sorted(items, key=lambda row: row.reel_item_id):
        direct_definition = definition_for_item(item)
        direct_key = direct_definition.candidate_key if direct_definition else ""
        direct_title = direct_definition.title if direct_definition else ""
        direct_candidate_status = "none"
        direct_candidate_failures: list[str] = []
        direct_candidate_metrics: dict[str, Any] = {}
        if direct_key in published_by_key:
            direct_candidate_status = "published"
            direct_candidate_metrics = published_by_key[direct_key].get("metrics", {})
        elif direct_key in rejected_by_key:
            direct_candidate_status = "rejected_after_recall"
            direct_candidate_failures = rejected_by_key[direct_key].get("failures", [])
            direct_candidate_metrics = rejected_by_key[direct_key].get("metrics", {})
        elif direct_key in hidden_by_key:
            direct_candidate_status = "hidden_candidate"
            direct_candidate_failures = hidden_by_key[direct_key].get("failures", [])
            direct_candidate_metrics = hidden_by_key[direct_key].get("metrics", {})

        best_published, best_published_score, best_published_reasons = best_definition_match(item, published_definitions)
        best_any, best_any_score, best_any_reasons = best_definition_match(item, seed_definitions)
        assignment = assignment_by_item_id.get(item.reel_item_id)
        if assignment:
            visibility = "published"
            model_reason = "included_in_visible_strong_list"
        elif not direct_definition:
            visibility = "search_only"
            model_reason = "no_structured_candidate"
        elif direct_candidate_status == "hidden_candidate":
            visibility = "search_only"
            model_reason = "candidate_failed_publish_gate"
        elif direct_candidate_status == "rejected_after_recall":
            visibility = "search_only"
            model_reason = "candidate_rejected_after_recall"
        elif best_published_score < RECALL_MEMBER_SCORE:
            visibility = "search_only"
            model_reason = "below_recall_threshold_for_visible_lists"
        else:
            visibility = "search_only"
            model_reason = "not_selected_by_final_visible_lists"

        audit_rows.append(
            {
                **item_payload(item),
                "visibility": visibility,
                "published_list": assignment.get("list_title", "") if assignment else "",
                "published_membership_score": assignment.get("membership_score", "") if assignment else "",
                "model_reason": model_reason,
                "direct_candidate": direct_title,
                "direct_candidate_status": direct_candidate_status,
                "direct_candidate_failures": direct_candidate_failures,
                "direct_candidate_item_count": direct_candidate_metrics.get("item_count", ""),
                "direct_candidate_purity": direct_candidate_metrics.get("purity", ""),
                "direct_candidate_avg_similarity": direct_candidate_metrics.get("avg_pairwise_similarity", ""),
                "direct_candidate_min_similarity": direct_candidate_metrics.get("min_pairwise_similarity", ""),
                "best_published_candidate": best_published.title if best_published else "",
                "best_published_score": best_published_score,
                "best_published_reasons": best_published_reasons,
                "best_any_candidate": best_any.title if best_any else "",
                "best_any_score": best_any_score,
                "best_any_reasons": best_any_reasons,
            }
        )
    return audit_rows


def build_strong_personalization(items: list[Item]) -> dict[str, Any]:
    seed_groups: dict[str, dict[str, Any]] = {}
    search_only_ids = set()

    for item in items:
        definition = definition_for_item(item)
        if not definition:
            search_only_ids.add(item.reel_item_id)
            continue
        group = seed_groups.setdefault(
            definition.candidate_key,
            {"definition": definition, "seed_items": []},
        )
        group["seed_items"].append(item)

    published_definitions: list[CandidateDefinition] = []
    candidate_reports = []
    hidden_candidates = []
    for group in seed_groups.values():
        definition = group["definition"]
        seed_items = group["seed_items"]
        metrics = candidate_metrics(seed_items, definition)
        publish, failures = should_publish(metrics, enforce_min_pairwise=False)
        report = {
            "candidate_key": definition.candidate_key,
            "title": definition.title,
            "family": definition.family,
            "definition": definition_payload(definition),
            "metrics": metrics,
            "publish": publish,
            "failures": failures,
            "seed_item_ids": [item.reel_item_id for item in seed_items],
        }
        candidate_reports.append(report)
        if publish:
            published_definitions.append(definition)
        else:
            hidden_candidates.append(report)

    assigned: dict[int, tuple[CandidateDefinition, float, dict[str, float]]] = {}
    candidate_members: dict[str, list[tuple[Item, float, dict[str, float]]]] = defaultdict(list)
    for item in items:
        best: tuple[CandidateDefinition, float, dict[str, float]] | None = None
        for definition in published_definitions:
            score, reasons = membership_score(item, definition)
            if score < RECALL_MEMBER_SCORE:
                continue
            if best is None or score > best[1]:
                best = (definition, score, reasons)
        if best:
            current = assigned.get(item.reel_item_id)
            if not current or best[1] > current[1]:
                assigned[item.reel_item_id] = best

    for item in items:
        assignment = assigned.get(item.reel_item_id)
        if assignment:
            definition, score, reasons = assignment
            candidate_members[definition.candidate_key].append((item, score, reasons))

    published_lists = []
    rejected_after_recall = []
    for definition in published_definitions:
        members = sorted(
            candidate_members.get(definition.candidate_key, []),
            key=lambda row: (-row[1], row[0].item_name.lower(), row[0].reel_item_id),
        )
        final_items = [item for item, _score, _reasons in members]
        metrics = candidate_metrics(final_items, definition) if final_items else {}
        row = {
            "title": definition.title,
            "candidate_key": definition.candidate_key,
            "definition": definition_payload(definition),
            "metrics": metrics,
            "items": [
                item_payload(item, score, reasons)
                for item, score, reasons in members
            ],
        }
        final_publish, final_failures = should_publish(metrics, enforce_min_pairwise=True, definition=definition)
        if final_publish:
            published_lists.append(row)
        else:
            rejected_after_recall.append({**row, "failures": final_failures})
    published_ids = {
        item["reel_item_id"]
        for collection in published_lists
        for item in collection["items"]
    }
    search_only = [item for item in items if item.reel_item_id not in published_ids]
    item_audit = build_item_audit(items, published_lists, hidden_candidates, rejected_after_recall, seed_groups)

    return {
        "model": "strong_personalization_v1",
        "principle": "Publish only strong repeated interests; keep all other reels search-only.",
        "thresholds": {
            "min_items_to_publish": MIN_ITEMS_TO_PUBLISH,
            "min_avg_pairwise_similarity": MIN_AVG_PAIRWISE_SIMILARITY,
            "min_pairwise_similarity": MIN_PAIRWISE_SIMILARITY,
            "min_location_food_pairwise_similarity": MIN_LOCATION_FOOD_PAIRWISE_SIMILARITY,
            "min_purity": MIN_PURITY,
            "min_member_score": MIN_MEMBER_SCORE,
            "recall_member_score": RECALL_MEMBER_SCORE,
        },
        "summary": {
            "total_items": len(items),
            "published_list_count": len(published_lists),
            "published_item_count": len(published_ids),
            "search_only_item_count": len(search_only),
            "visible_coverage": round(len(published_ids) / max(len(items), 1), 4),
            "hidden_candidate_count": len(hidden_candidates),
            "rejected_after_recall_count": len(rejected_after_recall),
        },
        "published_lists": sorted(
            published_lists,
            key=lambda row: (-row["metrics"].get("item_count", 0), row["title"].lower()),
        ),
        "hidden_candidates": sorted(
            hidden_candidates,
            key=lambda row: (-row["metrics"]["item_count"], row["title"].lower()),
        ),
        "rejected_after_recall": sorted(
            rejected_after_recall,
            key=lambda row: (-row["metrics"].get("item_count", 0), row["title"].lower()),
        ),
        "search_only_items": [item_payload(item) for item in sorted(search_only, key=lambda row: row.reel_item_id)],
        "item_audit": item_audit,
        "candidate_benchmark": sorted(
            candidate_reports,
            key=lambda row: (-row["metrics"]["item_count"], row["title"].lower()),
        ),
    }


def definition_payload(definition: CandidateDefinition) -> dict[str, Any]:
    return {
        "title": definition.title,
        "family": definition.family,
        "canonical_domain": definition.canonical_domain,
        "location": definition.location,
        "allowed_labels": sorted(definition.allowed_labels),
        "allowed_domains": sorted(definition.allowed_domains),
        "allowed_item_types": sorted(definition.allowed_item_types),
        "allowed_intents": sorted(definition.allowed_intents),
        "required_location": definition.required_location,
    }


def write_outputs(payload: dict[str, Any], output_dir: Path, user_id: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{user_id}_strong_personalization.json"
    csv_path = output_dir / f"{user_id}_published_lists.csv"
    benchmark_path = output_dir / f"{user_id}_candidate_benchmark.csv"
    audit_csv_path = output_dir / f"{user_id}_full_set_audit.csv"
    audit_html_path = output_dir / f"{user_id}_full_set_audit.html"
    review_html_path = output_dir / f"{user_id}_review_viewer.html"
    html_path = output_dir / f"{user_id}_strong_personalization.html"

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_published_csv(payload, csv_path)
    write_benchmark_csv(payload, benchmark_path)
    write_audit_csv(payload, audit_csv_path)
    html_path.write_text(render_html(payload, user_id), encoding="utf-8")
    audit_html_path.write_text(render_audit_html(payload, user_id), encoding="utf-8")
    review_html_path.write_text(render_review_viewer_html(payload, user_id), encoding="utf-8")
    return {
        "json": str(json_path),
        "published_csv": str(csv_path),
        "benchmark_csv": str(benchmark_path),
        "audit_csv": str(audit_csv_path),
        "html": str(html_path),
        "audit_html": str(audit_html_path),
        "review_html": str(review_html_path),
    }


def write_published_csv(payload: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "list_title",
        "item_count",
        "purity",
        "avg_pairwise_similarity",
        "membership_score",
        "reel_item_id",
        "item_name",
        "summary",
        "url",
        "domain",
        "subdomains",
        "location",
        "intent",
        "item_type",
        "product_name",
        "brand",
    ]
    with path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for collection in payload["published_lists"]:
            metrics = collection["metrics"]
            for item in collection["items"]:
                writer.writerow(
                    {
                        "list_title": collection["title"],
                        "item_count": metrics.get("item_count", ""),
                        "purity": metrics.get("purity", ""),
                        "avg_pairwise_similarity": metrics.get("avg_pairwise_similarity", ""),
                        "membership_score": item.get("membership_score", ""),
                        "reel_item_id": item["reel_item_id"],
                        "item_name": item["item_name"],
                        "summary": item["summary"],
                        "url": item["url"],
                        "domain": item["canonical_domain"],
                        "subdomains": " | ".join(item["subdomains"]),
                        "location": item["location"],
                        "intent": item["intent"],
                        "item_type": item["item_type"],
                        "product_name": item["product_name"],
                        "brand": item["brand"],
                    }
                )


def write_benchmark_csv(payload: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "title",
        "publish",
        "failures",
        "item_count",
        "purity",
        "avg_member_score",
        "min_member_score",
        "avg_pairwise_similarity",
        "min_pairwise_similarity",
        "family",
        "location",
        "allowed_labels",
    ]
    with path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload["candidate_benchmark"]:
            metrics = row["metrics"]
            definition = row["definition"]
            writer.writerow(
                {
                    "title": row["title"],
                    "publish": "yes" if row["publish"] else "no",
                    "failures": " | ".join(row["failures"]),
                    "item_count": metrics["item_count"],
                    "purity": metrics["purity"],
                    "avg_member_score": metrics["avg_member_score"],
                    "min_member_score": metrics["min_member_score"],
                    "avg_pairwise_similarity": metrics["avg_pairwise_similarity"],
                    "min_pairwise_similarity": metrics["min_pairwise_similarity"],
                    "family": row["family"],
                    "location": definition["location"],
                    "allowed_labels": " | ".join(definition["allowed_labels"]),
                }
            )


def write_audit_csv(payload: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "visibility",
        "published_list",
        "published_membership_score",
        "model_reason",
        "reel_item_id",
        "reel_id",
        "item_name",
        "summary",
        "url",
        "canonical_domain",
        "subdomains",
        "location",
        "intent",
        "item_type",
        "entities",
        "product_name",
        "brand",
        "direct_candidate",
        "direct_candidate_status",
        "direct_candidate_failures",
        "direct_candidate_item_count",
        "direct_candidate_purity",
        "direct_candidate_avg_similarity",
        "direct_candidate_min_similarity",
        "best_published_candidate",
        "best_published_score",
        "best_published_reasons",
        "best_any_candidate",
        "best_any_score",
        "best_any_reasons",
    ]
    with path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload.get("item_audit", []):
            writer.writerow(
                {
                    **{field: row.get(field, "") for field in fieldnames},
                    "subdomains": " | ".join(row.get("subdomains", [])),
                    "entities": " | ".join(row.get("entities", [])),
                    "direct_candidate_failures": " | ".join(row.get("direct_candidate_failures", [])),
                    "best_published_reasons": json.dumps(row.get("best_published_reasons", {}), ensure_ascii=False),
                    "best_any_reasons": json.dumps(row.get("best_any_reasons", {}), ensure_ascii=False),
                }
            )


def grouped_audit_rows(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload.get("item_audit", []):
        if row.get("visibility") == "published":
            grouped[f"Published: {row.get('published_list') or 'Unknown'}"].append(row)
        else:
            reason = row.get("model_reason") or "search_only"
            candidate = row.get("direct_candidate") or row.get("best_any_candidate") or "No candidate"
            grouped[f"Search-only: {reason} / {candidate}"].append(row)
    return dict(sorted(grouped.items(), key=lambda item: (0 if item[0].startswith("Published") else 1, item[0].lower())))


def render_audit_row(row: dict[str, Any]) -> str:
    status_class = "published" if row.get("visibility") == "published" else "search-only"
    target = row.get("published_list") or row.get("direct_candidate") or row.get("best_any_candidate") or "No candidate"
    score = row.get("published_membership_score")
    if score == "":
        score = row.get("best_published_score", "")
    failures = ", ".join(row.get("direct_candidate_failures", []))
    return f"""
    <article class="audit-item {status_class}">
      <div class="rail">
        <span>{html.escape(row.get("visibility", ""))}</span>
        <b>{html.escape(str(score))}</b>
      </div>
      <div class="body">
        <h3>{html.escape(row.get("item_name") or "Untitled item")}</h3>
        <p>{html.escape(row.get("summary", ""))}</p>
        <div class="chips">
          <span>{html.escape(row.get("canonical_domain", ""))}</span>
          <span>{html.escape(row.get("location") or "no location")}</span>
          <span>{html.escape(row.get("intent", ""))}</span>
          <span>{html.escape(", ".join(row.get("subdomains", [])) or "no subdomain")}</span>
        </div>
        <dl>
          <div><dt>Target</dt><dd>{html.escape(target)}</dd></div>
          <div><dt>Reason</dt><dd>{html.escape(row.get("model_reason", ""))}</dd></div>
          <div><dt>Candidate status</dt><dd>{html.escape(row.get("direct_candidate_status", ""))}</dd></div>
          <div><dt>Failures</dt><dd>{html.escape(failures or "none")}</dd></div>
          <div><dt>Best visible match</dt><dd>{html.escape(row.get("best_published_candidate", ""))} ({html.escape(str(row.get("best_published_score", "")))})</dd></div>
        </dl>
        <a href="{html.escape(row.get("url", ""))}" target="_blank" rel="noreferrer">{html.escape(row.get("url", ""))}</a>
      </div>
    </article>
    """


def render_audit_html(payload: dict[str, Any], user_id: str) -> str:
    summary = payload["summary"]
    reason_counts = Counter(row.get("model_reason", "") for row in payload.get("item_audit", []))
    domain_counts = Counter(
        row.get("canonical_domain", "")
        for row in payload.get("item_audit", [])
        if row.get("visibility") != "published"
    )
    reason_cards = "".join(
        f"<div class='mini'><span>{html.escape(reason)}</span><b>{count}</b></div>"
        for reason, count in reason_counts.most_common()
    )
    domain_cards = "".join(
        f"<div class='mini'><span>{html.escape(domain or 'Unknown')}</span><b>{count}</b></div>"
        for domain, count in domain_counts.most_common(10)
    )
    sections = []
    for title, rows in grouped_audit_rows(payload).items():
        sections.append(
            f"""
            <section class="group">
              <header>
                <h2>{html.escape(title)}</h2>
                <span>{len(rows)} items</span>
              </header>
              {''.join(render_audit_row(row) for row in rows)}
            </section>
            """
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Full Set Audit - {html.escape(user_id)}</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#101217; color:#f6f7f9; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; padding:28px; background:#101217; }}
    main {{ max-width:1280px; margin:0 auto; }}
    h1 {{ margin:0 0 6px; font-size:34px; }}
    .sub {{ margin:0 0 22px; color:#aab2bf; }}
    .stats {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-bottom:16px; }}
    .stat, .mini, .group {{ background:#191d25; border:1px solid #2a303b; border-radius:8px; }}
    .stat {{ padding:15px; }}
    .stat span, .mini span {{ color:#aab2bf; font-size:13px; }}
    .stat b {{ display:block; font-size:28px; margin-top:5px; }}
    .strip {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin:0 0 20px; }}
    .mini-wrap {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }}
    .mini {{ padding:10px 12px; display:flex; justify-content:space-between; gap:12px; }}
    .panel-title {{ margin:4px 0 10px; color:#dfe5ee; font-size:15px; }}
    .group {{ margin:16px 0; overflow:hidden; }}
    .group header {{ position:sticky; top:0; display:flex; justify-content:space-between; align-items:center; gap:16px; padding:14px 16px; background:#202633; border-bottom:1px solid #313846; z-index:1; }}
    .group h2 {{ margin:0; font-size:19px; }}
    .group header span {{ color:#aab2bf; }}
    .audit-item {{ display:grid; grid-template-columns:96px 1fr; gap:14px; padding:14px 16px; border-bottom:1px solid #252b35; }}
    .audit-item:last-child {{ border-bottom:0; }}
    .audit-item.published .rail {{ background:#173023; color:#aef0c2; }}
    .audit-item.search-only .rail {{ background:#332819; color:#ffd49a; }}
    .rail {{ border-radius:7px; min-height:62px; display:flex; flex-direction:column; justify-content:center; align-items:center; gap:5px; text-align:center; padding:8px; }}
    .rail span {{ font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
    .rail b {{ font-size:16px; }}
    h3 {{ margin:0 0 6px; font-size:16px; }}
    p {{ margin:0 0 9px; color:#c9d0da; line-height:1.42; }}
    .chips {{ display:flex; flex-wrap:wrap; gap:6px; margin:8px 0; }}
    .chips span {{ border:1px solid #354052; color:#d8e0ea; border-radius:999px; padding:4px 8px; font-size:12px; }}
    dl {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:6px 16px; margin:8px 0; }}
    dl div {{ min-width:0; }}
    dt {{ color:#8f99a8; font-size:12px; }}
    dd {{ margin:2px 0 0; color:#dfe5ee; font-size:13px; overflow-wrap:anywhere; }}
    a {{ color:#9fd5c5; font-size:12px; word-break:break-all; }}
    @media (max-width: 760px) {{
      body {{ padding:16px; }}
      .stats, .strip, .mini-wrap, dl {{ grid-template-columns:1fr; }}
      .audit-item {{ grid-template-columns:1fr; }}
      .rail {{ align-items:flex-start; min-height:auto; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>Full Set Personalization Audit</h1>
    <p class="sub">User {html.escape(user_id)}. This shows every extracted item: published lists, search-only leftovers, and the reason each item landed there.</p>
    <section class="stats">
      <div class="stat"><span>Total items</span><b>{summary["total_items"]}</b></div>
      <div class="stat"><span>Published items</span><b>{summary["published_item_count"]}</b></div>
      <div class="stat"><span>Search-only items</span><b>{summary["search_only_item_count"]}</b></div>
      <div class="stat"><span>Visible coverage</span><b>{round(summary["visible_coverage"] * 100, 1)}%</b></div>
    </section>
    <section class="strip">
      <div>
        <h2 class="panel-title">Decision Reasons</h2>
        <div class="mini-wrap">{reason_cards}</div>
      </div>
      <div>
        <h2 class="panel-title">Search-Only Domains</h2>
        <div class="mini-wrap">{domain_cards}</div>
      </div>
    </section>
    {''.join(sections)}
  </main>
</body>
</html>
"""


def instagram_embed_url(url: str) -> str:
    value = normalize(url)
    if not value:
        return ""
    clean = value.split("?", 1)[0].rstrip("/")
    return f"{clean}/embed"


def review_item_card(item: dict[str, Any], list_title: str, index: int) -> str:
    url = item.get("url", "")
    embed_url = instagram_embed_url(url)
    subdomains = ", ".join(item.get("subdomains", []))
    meta_parts = [
        item.get("canonical_domain", ""),
        item.get("location", ""),
        item.get("intent", ""),
        subdomains,
    ]
    meta = " · ".join(part for part in meta_parts if part)
    return f"""
    <article
      class="reel-card"
      data-title="{html.escape((item.get("item_name") or "").lower())}"
      data-summary="{html.escape((item.get("summary") or "").lower())}"
      data-list="{html.escape(list_title.lower())}"
      data-url="{html.escape(url)}"
    >
      <div class="reel-main">
        <div class="rank">{index}</div>
        <div class="reel-copy">
          <h3>{html.escape(item.get("item_name") or "Untitled reel")}</h3>
          <p>{html.escape(item.get("summary") or "No summary available.")}</p>
          <div class="meta">{html.escape(meta or "No metadata")}</div>
          <div class="actions">
            <a class="button primary" href="{html.escape(url)}" target="_blank" rel="noreferrer">Open reel</a>
            <button class="button" type="button" data-preview="{html.escape(embed_url)}" data-name="{html.escape(item.get("item_name") or "Untitled reel")}">Preview here</button>
            <button class="button subtle" type="button" data-copy="{html.escape(url)}">Copy URL</button>
          </div>
          <div class="url">{html.escape(url)}</div>
        </div>
      </div>
    </article>
    """


def render_review_viewer_html(payload: dict[str, Any], user_id: str) -> str:
    published_sections = []
    nav_items = []
    total_grouped = 0
    for collection_index, collection in enumerate(payload.get("published_lists", []), start=1):
        title = collection["title"]
        items = collection.get("items", [])
        total_grouped += len(items)
        section_id = f"list-{collection_index}"
        nav_items.append((section_id, title, len(items), "grouped"))
        cards = "\n".join(review_item_card(item, title, index) for index, item in enumerate(items, start=1))
        published_sections.append(
            f"""
            <section class="list-section" id="{section_id}" data-section-title="{html.escape(title.lower())}">
              <header class="section-header">
                <div>
                  <span class="eyebrow">Grouped List</span>
                  <h2>{html.escape(title)}</h2>
                </div>
                <strong>{len(items)} reels</strong>
              </header>
              <div class="cards">{cards}</div>
            </section>
            """
        )

    ungrouped_items = payload.get("search_only_items", [])
    ungrouped_section_id = "ungrouped"
    nav_items.append((ungrouped_section_id, "Ungrouped / Search-only", len(ungrouped_items), "ungrouped"))
    ungrouped_cards = "\n".join(
        review_item_card(item, "Ungrouped / Search-only", index)
        for index, item in enumerate(ungrouped_items, start=1)
    )
    ungrouped_section = f"""
    <section class="list-section ungrouped" id="{ungrouped_section_id}" data-section-title="ungrouped search-only">
      <header class="section-header">
        <div>
          <span class="eyebrow">Ungrouped</span>
          <h2>Ungrouped / Search-only</h2>
        </div>
        <strong>{len(ungrouped_items)} reels</strong>
      </header>
      <div class="cards">{ungrouped_cards}</div>
    </section>
    """

    nav_html = "\n".join(
        f"""
        <a class="nav-row {kind}" href="#{html.escape(section_id)}">
          <span>{html.escape(title)}</span>
          <b>{count}</b>
        </a>
        """
        for section_id, title, count, kind in nav_items
    )
    summary = payload["summary"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ClipNest Review Viewer - {html.escape(user_id)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg:#0f1115;
      --panel:#181c23;
      --panel-2:#202631;
      --line:#2b3340;
      --text:#f4f6f8;
      --muted:#aab4c2;
      --green:#aee8c4;
      --blue:#9fc7ff;
      --yellow:#ffd38a;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{ margin:0; background:var(--bg); color:var(--text); }}
    .layout {{ display:grid; grid-template-columns:320px minmax(0,1fr) 420px; min-height:100vh; }}
    aside {{ position:sticky; top:0; height:100vh; overflow:auto; border-right:1px solid var(--line); background:#12161d; padding:20px; }}
    .brand h1 {{ margin:0; font-size:24px; }}
    .brand p {{ margin:6px 0 18px; color:var(--muted); line-height:1.4; }}
    .stats {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:16px; }}
    .stat {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:10px; }}
    .stat span {{ display:block; color:var(--muted); font-size:12px; }}
    .stat b {{ display:block; margin-top:4px; font-size:22px; }}
    .search {{ width:100%; background:#0d1015; color:var(--text); border:1px solid var(--line); border-radius:8px; padding:12px; font-size:14px; margin-bottom:14px; }}
    .nav-title {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; margin:14px 0 8px; }}
    .nav-row {{ display:flex; justify-content:space-between; gap:12px; text-decoration:none; color:var(--text); border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:10px 11px; margin-bottom:8px; }}
    .nav-row span {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .nav-row b {{ min-width:32px; text-align:center; color:var(--green); }}
    .nav-row.ungrouped b {{ color:var(--yellow); }}
    main {{ padding:26px; min-width:0; }}
    .topline {{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin-bottom:18px; }}
    .topline h1 {{ margin:0; font-size:30px; }}
    .topline p {{ margin:6px 0 0; color:var(--muted); }}
    .counter {{ color:var(--muted); }}
    .list-section {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; margin-bottom:22px; overflow:hidden; }}
    .section-header {{ position:sticky; top:0; z-index:2; display:flex; align-items:center; justify-content:space-between; gap:16px; padding:16px 18px; background:var(--panel-2); border-bottom:1px solid var(--line); }}
    .section-header h2 {{ margin:2px 0 0; font-size:22px; }}
    .section-header strong {{ color:var(--green); font-size:16px; white-space:nowrap; }}
    .ungrouped .section-header strong {{ color:var(--yellow); }}
    .eyebrow {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }}
    .cards {{ padding:4px 18px 8px; }}
    .reel-card {{ border-bottom:1px solid var(--line); padding:14px 0; }}
    .reel-card:last-child {{ border-bottom:0; }}
    .reel-main {{ display:grid; grid-template-columns:42px 1fr; gap:13px; }}
    .rank {{ width:34px; height:34px; display:grid; place-items:center; border-radius:8px; background:#273040; color:var(--blue); font-weight:700; }}
    .reel-copy h3 {{ margin:0 0 7px; font-size:17px; }}
    .reel-copy p {{ margin:0 0 9px; color:#d2d8e2; line-height:1.45; }}
    .meta {{ color:var(--muted); font-size:12px; margin-bottom:10px; }}
    .actions {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:8px; }}
    .button {{ appearance:none; border:1px solid var(--line); background:#252c38; color:var(--text); border-radius:7px; padding:8px 10px; font-size:13px; text-decoration:none; cursor:pointer; }}
    .button.primary {{ background:#1e3a2d; border-color:#315f49; color:var(--green); }}
    .button.subtle {{ color:var(--muted); }}
    .url {{ color:#7f8a99; font-size:12px; word-break:break-all; }}
    .preview {{ position:sticky; top:0; height:100vh; border-left:1px solid var(--line); background:#12161d; padding:20px; overflow:auto; }}
    .preview h2 {{ margin:0 0 10px; font-size:20px; }}
    .preview p {{ color:var(--muted); line-height:1.45; }}
    .frame-wrap {{ width:100%; aspect-ratio:9/16; background:#0b0d11; border:1px solid var(--line); border-radius:8px; overflow:hidden; display:grid; place-items:center; }}
    iframe {{ width:100%; height:100%; border:0; background:#0b0d11; }}
    .empty-preview {{ padding:18px; text-align:center; color:var(--muted); }}
    .hidden {{ display:none !important; }}
    @media (max-width: 1120px) {{
      .layout {{ grid-template-columns:280px minmax(0,1fr); }}
      .preview {{ display:none; }}
    }}
    @media (max-width: 760px) {{
      .layout {{ display:block; }}
      aside {{ position:relative; height:auto; border-right:0; border-bottom:1px solid var(--line); }}
      main {{ padding:16px; }}
      .topline {{ display:block; }}
      .section-header {{ top:0; }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <aside>
      <div class="brand">
        <h1>ClipNest Review</h1>
        <p>Open reels list by list. Ungrouped reels are at the bottom.</p>
      </div>
      <div class="stats">
        <div class="stat"><span>Total</span><b>{summary["total_items"]}</b></div>
        <div class="stat"><span>Grouped</span><b>{total_grouped}</b></div>
        <div class="stat"><span>Ungrouped</span><b>{len(ungrouped_items)}</b></div>
        <div class="stat"><span>Lists</span><b>{len(payload.get("published_lists", []))}</b></div>
      </div>
      <input id="search" class="search" type="search" placeholder="Search item, list, summary, URL..." />
      <div class="nav-title">Folders</div>
      <nav>{nav_html}</nav>
    </aside>
    <main>
      <div class="topline">
        <div>
          <h1>Grouped Reels</h1>
          <p>Simple viewer for checking which reels entered which folder.</p>
        </div>
        <div id="visibleCount" class="counter">{summary["total_items"]} visible</div>
      </div>
      {''.join(published_sections)}
      {ungrouped_section}
    </main>
    <section class="preview">
      <h2>Preview</h2>
      <p>Click “Preview here” on any reel. If Instagram blocks the embed, use “Open reel”.</p>
      <div class="frame-wrap" id="previewFrame">
        <div class="empty-preview">No reel selected.</div>
      </div>
    </section>
  </div>
  <script>
    const search = document.getElementById('search');
    const visibleCount = document.getElementById('visibleCount');
    const cards = Array.from(document.querySelectorAll('.reel-card'));
    const sections = Array.from(document.querySelectorAll('.list-section'));
    const previewFrame = document.getElementById('previewFrame');

    function updateSearch() {{
      const term = search.value.trim().toLowerCase();
      let count = 0;
      for (const card of cards) {{
        const haystack = [
          card.dataset.title || '',
          card.dataset.summary || '',
          card.dataset.list || '',
          card.dataset.url || '',
          card.textContent.toLowerCase()
        ].join(' ');
        const match = !term || haystack.includes(term);
        card.classList.toggle('hidden', !match);
        if (match) count += 1;
      }}
      for (const section of sections) {{
        const hasVisible = !!section.querySelector('.reel-card:not(.hidden)');
        const titleMatch = !term || (section.dataset.sectionTitle || '').includes(term);
        section.classList.toggle('hidden', !(hasVisible || titleMatch));
      }}
      visibleCount.textContent = `${{count}} visible`;
    }}

    document.addEventListener('click', async (event) => {{
      const previewButton = event.target.closest('[data-preview]');
      if (previewButton) {{
        const src = previewButton.dataset.preview;
        const name = previewButton.dataset.name || 'Selected reel';
        previewFrame.innerHTML = src
          ? `<iframe src="${{src}}" title="${{name}}" loading="lazy" allowfullscreen></iframe>`
          : '<div class="empty-preview">Preview URL unavailable.</div>';
      }}
      const copyButton = event.target.closest('[data-copy]');
      if (copyButton) {{
        try {{
          await navigator.clipboard.writeText(copyButton.dataset.copy || '');
          copyButton.textContent = 'Copied';
          setTimeout(() => copyButton.textContent = 'Copy URL', 1000);
        }} catch (error) {{
          copyButton.textContent = 'Copy failed';
          setTimeout(() => copyButton.textContent = 'Copy URL', 1000);
        }}
      }}
    }});

    search.addEventListener('input', updateSearch);
  </script>
</body>
</html>
"""


def render_html(payload: dict[str, Any], user_id: str) -> str:
    summary = payload["summary"]
    cards = []
    for collection in payload["published_lists"]:
        metrics = collection["metrics"]
        items = "\n".join(
            f"""
            <article class="item">
              <div class="score">{html.escape(str(item.get("membership_score", "")))}</div>
              <div>
                <h3>{html.escape(item["item_name"] or "Untitled item")}</h3>
                <p>{html.escape(item["summary"])}</p>
                <a href="{html.escape(item["url"])}" target="_blank" rel="noreferrer">{html.escape(item["url"])}</a>
                <div class="meta">{html.escape(item["canonical_domain"])} · {html.escape(item["location"] or "no location")} · {html.escape(", ".join(item["subdomains"]))}</div>
              </div>
            </article>
            """
            for item in collection["items"]
        )
        cards.append(
            f"""
            <section class="list">
              <header>
                <h2>{html.escape(collection["title"])}</h2>
                <div class="badges">
                  <span>{metrics.get("item_count", 0)} items</span>
                  <span>purity {metrics.get("purity", 0)}</span>
                  <span>similarity {metrics.get("avg_pairwise_similarity", 0)}</span>
                </div>
              </header>
              {items}
            </section>
            """
        )
    hidden_rows = "\n".join(
        f"<tr><td>{html.escape(row['title'])}</td><td>{row['metrics']['item_count']}</td><td>{row['metrics']['purity']}</td><td>{row['metrics']['avg_pairwise_similarity']}</td><td>{html.escape(', '.join(row['failures']))}</td></tr>"
        for row in payload["hidden_candidates"][:30]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Strong Personalization - {html.escape(user_id)}</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#111318; color:#f4f6f8; }}
    body {{ margin:0; padding:32px; background:#111318; }}
    .shell {{ max-width:1180px; margin:0 auto; }}
    h1 {{ font-size:32px; margin:0 0 8px; }}
    .sub {{ color:#aeb6c2; margin:0 0 24px; }}
    .stats {{ display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:12px; margin-bottom:28px; }}
    .stat, .list, .hidden {{ background:#191d25; border:1px solid #2b313d; border-radius:8px; padding:16px; }}
    .stat b {{ display:block; font-size:26px; margin-top:6px; }}
    .list {{ margin-bottom:18px; }}
    .list header {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; border-bottom:1px solid #2b313d; padding-bottom:12px; margin-bottom:12px; }}
    h2 {{ margin:0; font-size:22px; }}
    .badges {{ display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-end; }}
    .badges span {{ background:#253044; color:#d9e6ff; border-radius:999px; padding:5px 9px; font-size:12px; }}
    .item {{ display:grid; grid-template-columns:64px 1fr; gap:12px; padding:12px 0; border-bottom:1px solid #252b35; }}
    .item:last-child {{ border-bottom:0; }}
    .score {{ width:48px; height:32px; display:grid; place-items:center; background:#22301f; color:#bdf0a8; border-radius:6px; font-variant-numeric:tabular-nums; }}
    h3 {{ margin:0 0 6px; font-size:16px; }}
    p {{ margin:0 0 8px; color:#cdd4df; line-height:1.45; }}
    a {{ color:#9fd5c5; word-break:break-all; font-size:13px; }}
    .meta {{ color:#8d96a3; font-size:12px; margin-top:6px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ text-align:left; padding:9px; border-bottom:1px solid #2b313d; color:#cdd4df; }}
    th {{ color:#f4f6f8; }}
  </style>
</head>
<body>
  <main class="shell">
    <h1>Strong Personalization Prototype</h1>
    <p class="sub">User {html.escape(user_id)}. Only strong repeated interests are visible; everything else remains search-only.</p>
    <section class="stats">
      <div class="stat">Total items<b>{summary["total_items"]}</b></div>
      <div class="stat">Published lists<b>{summary["published_list_count"]}</b></div>
      <div class="stat">Published items<b>{summary["published_item_count"]}</b></div>
      <div class="stat">Search-only items<b>{summary["search_only_item_count"]}</b></div>
    </section>
    {''.join(cards)}
    <section class="hidden">
      <h2>Hidden Candidates</h2>
      <p class="sub">These were found but not published because they failed the strength benchmark.</p>
      <table>
        <thead><tr><th>Candidate</th><th>Items</th><th>Purity</th><th>Similarity</th><th>Failures</th></tr></thead>
        <tbody>{hidden_rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build strong-list personalization output without reprocessing reels.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--user-id", default="default")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    items = load_items(args.db, args.user_id)
    payload = build_strong_personalization(items)
    payload["user_id"] = args.user_id
    payload["db_path"] = str(args.db)
    paths = write_outputs(payload, args.output_dir, args.user_id)
    print(json.dumps({"summary": payload["summary"], "paths": paths}, indent=2))


if __name__ == "__main__":
    main()
