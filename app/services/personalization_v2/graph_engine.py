from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from app.services.personalization_v2.embeddings import cosine_similarity, embed_text
from app.services.personalization_v2.models import AssignmentDecision, ClusterCandidate, StructuredFeature
from app.services.personalization_v2.repository import PersonalizationV2Repository
from app.services.personalization_v2.split_merge import merge_score_between_clusters, split_score_for_cluster


ASSIGNMENT_VERSION = "v2-phase2"

LOCATION_CLUSTER_SUBDOMAINS = {
    "restaurants",
    "seafood restaurants",
    "street food",
    "cafes",
    "late-night food",
    "restaurant",
    "stay",
    "travel planning",
    "cultural experience",
    "travel utility",
    "destinations",
}
TITLE_OVERRIDES = {
    "films and shows": "Films & Shows",
    "music": "Music",
    "photo ideas": "Photo Ideas",
    "fragrance": "Fragrances",
    "fitness": "Fitness",
    "wellness": "Wellness & Advice",
    "travel planning": "Travel Planning",
    "cultural experience": "Travel Perspectives",
    "travel utility": "Travel Tools",
    "app": "Apps & Tools",
    "ai": "AI & Future Tech",
    "audio device": "Audio Devices",
    "kitchen device": "Kitchen Devices",
    "device": "Gadgets & Devices",
    "consumer tech": "Consumer Tech",
    "marketing": "Marketing Ideas",
    "business and money": "Business & Money",
    "beauty and style": "Beauty & Style",
    "men's clothing brands": "Men's Clothing Brands",
    "luxury outlet shopping": "Luxury Outlet Shopping",
    "sneaker culture": "Sneaker Culture",
    "lifestyle ideas": "Lifestyle Ideas",
    "restaurants": "Restaurants",
    "seafood restaurants": "Seafood Restaurants",
    "street food": "Street Food",
    "cafes": "Cafes",
    "late-night food": "Late-Night Food",
    "destinations": "Travel Destinations",
    "protein recipes": "Protein Recipes",
    "recipes": "Recipes",
    "job search tools": "Job Search Tools",
    "wealth education": "Wealth Education",
    "money making ideas": "Money-Making Ideas",
    "startup advice": "Startup Advice",
    "motivation and mindset": "Motivation & Mindset",
    "advice": "Advice",
    "fitness accessories": "Fitness Accessories",
    "local rentals": "Local Rentals",
    "humor": "Entertainment Humor",
    "commentary": "Entertainment Commentary",
    "innovation": "Technology Innovation",
    "learning app": "Learning Apps",
    "local food": "Local Food",
}

PLACE_FOOD_LABELS = {
    "restaurants",
    "restaurant",
    "seafood restaurants",
    "street food",
    "cafes",
    "late-night food",
    "dessert spots",
    "local food",
}


def as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple) or isinstance(value, set):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [str(key).strip() for key in value.keys() if str(key).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def feature_embedding_text(feature: StructuredFeature) -> str:
    subdomains = as_list(feature.subdomains)
    entities = as_list(feature.entities)
    parts = [
        feature.canonical_domain,
        feature.location,
        ", ".join(subdomains),
        feature.item_type,
        feature.intent,
        feature.item_name,
        feature.summary,
        ", ".join(entities),
    ]
    return " | ".join(part for part in parts if part)


def stable_hash(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()


def recency_weight(received_at: str) -> float:
    try:
        timestamp = datetime.fromisoformat(received_at)
    except Exception:
        return 0.0
    age_days = max((datetime.now() - timestamp).days, 0)
    return max(0.0, 1.0 - min(age_days / 30.0, 1.0))


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    union = len(left | right)
    if union == 0:
        return 0.0
    return overlap / union


def overlap_score(feature: StructuredFeature, candidate: ClusterCandidate) -> tuple[float, dict]:
    metadata = candidate.metadata or {}
    feature_subdomains = set(as_list(feature.subdomains))
    candidate_subdomains = set(as_list(metadata.get("top_subdomains", [])))
    feature_entities = set(as_list(feature.entities))
    candidate_entities = set(as_list(metadata.get("top_entities", [])))
    domain_match = 1.0 if feature.canonical_domain == metadata.get("canonical_domain", feature.canonical_domain) else 0.0
    subdomains_score = jaccard(feature_subdomains, candidate_subdomains)
    location_score = 1.0 if feature.location and feature.location == metadata.get("top_location", "") else 0.0
    entity_score = jaccard(feature_entities, candidate_entities)
    item_type_score = 1.0 if feature.item_type and feature.item_type == metadata.get("item_type_mode", "") else 0.0
    intent_score = 1.0 if feature.intent and feature.intent == metadata.get("intent_mode", "") else 0.0
    embedding_score = cosine_similarity(feature.embedding_vector, candidate.embedding_vector)
    growth_score = min(candidate.growth_velocity, 1.0)
    final_score = (
        domain_match * 0.22 +
        subdomains_score * 0.18 +
        location_score * 0.18 +
        entity_score * 0.14 +
        item_type_score * 0.08 +
        intent_score * 0.08 +
        growth_score * 0.07 +
        embedding_score * 0.05
    )
    return final_score, {
        "domain_match": domain_match,
        "subdomain_overlap": subdomains_score,
        "location_match": location_score,
        "entity_overlap": entity_score,
        "item_type_match": item_type_score,
        "intent_match": intent_score,
        "growth_support": growth_score,
        "embedding_similarity": embedding_score,
    }


def primary_subdomain(subdomains: list[str], item_type: str = "") -> str:
    ordered = as_list(subdomains)
    if item_type == "product":
        product_first = [
            "luxury outlet shopping",
            "audio device",
            "kitchen device",
            "device",
            "fragrance",
            "men's clothing brands",
            "sneaker culture",
            "beauty and style",
            "fitness accessories",
        ]
        for label in product_first:
            if label in ordered:
                return label
    if item_type == "app":
        app_first = ["app", "learning app", "job search tools", "ai"]
        for label in app_first:
            if label in ordered:
                return label
    preferred = [
        "street food",
        "seafood restaurants",
        "cafes",
        "late-night food",
        "restaurants",
        "restaurant",
        "stay",
        "travel planning",
        "destinations",
        "protein recipes",
        "recipes",
        "recipe",
        "films and shows",
        "music",
        "photo ideas",
        "fragrance",
        "fitness",
        "wellness",
        "beauty and style",
        "men's clothing brands",
        "luxury outlet shopping",
        "sneaker culture",
        "lifestyle ideas",
        "audio device",
        "kitchen device",
        "device",
        "app",
        "ai",
        "consumer tech",
        "job search tools",
        "wealth education",
        "money making ideas",
        "startup advice",
        "motivation and mindset",
        "advice",
        "fitness accessories",
        "local rentals",
        "marketing",
        "business and money",
        "travel utility",
        "cultural experience",
        "internet culture",
    ]
    for label in preferred:
        if label in ordered:
            return label
    if ordered:
        return ordered[0]
    return item_type or ""


def cross_domain_family_bucket(bucket: str) -> bool:
    return bucket in {"apps_and_tools", "tech_products"}


def should_scope_cluster_by_location(domain: str, subdomains: list[str], item_type: str) -> bool:
    label = primary_subdomain(subdomains, item_type)
    if domain in {"Travel & Food", "Food & Local Eats", "Travel Accommodations", "Travel Destinations", "Travel"}:
        return label in LOCATION_CLUSTER_SUBDOMAINS or item_type == "place"
    if domain == "Lifestyle":
        return label == "luxury outlet shopping"
    return False


def title_override_for_subdomain(subdomain: str) -> str:
    return TITLE_OVERRIDES.get(subdomain, subdomain.title())


def cluster_key_for_feature(feature: StructuredFeature) -> str:
    subdomains = as_list(feature.subdomains)
    chosen_subdomain = primary_subdomain(subdomains, feature.item_type)
    parts = [feature.canonical_domain]
    if feature.location and should_scope_cluster_by_location(feature.canonical_domain, subdomains, feature.item_type):
        parts.append(feature.location)
    elif chosen_subdomain:
        parts.append(chosen_subdomain)
    if chosen_subdomain:
        parts.append(chosen_subdomain)
    elif feature.item_type:
        parts.append(feature.item_type)
    return " :: ".join(dict.fromkeys(part for part in parts if part))


def cluster_display_hint(feature: StructuredFeature) -> str:
    subdomains = as_list(feature.subdomains)
    chosen_subdomain = primary_subdomain(subdomains, feature.item_type)
    title = title_override_for_subdomain(chosen_subdomain) if chosen_subdomain else feature.canonical_domain
    if feature.location and should_scope_cluster_by_location(feature.canonical_domain, subdomains, feature.item_type):
        if chosen_subdomain in {"restaurant", "restaurants"}:
            return f"Restaurants in {feature.location}"
        if chosen_subdomain == "seafood restaurants":
            return f"Seafood Restaurants in {feature.location}"
        if chosen_subdomain == "street food":
            return f"Street Food in {feature.location}"
        if chosen_subdomain == "cafes":
            return f"Cafes in {feature.location}"
        if chosen_subdomain == "late-night food":
            return f"Late-Night Food in {feature.location}"
        if chosen_subdomain == "stay":
            return f"{feature.location} Stay"
        if chosen_subdomain == "destinations":
            return feature.location
        return f"{feature.location} {title}"
    if feature.location:
        return feature.location
    if chosen_subdomain:
        return title
    if subdomains:
        return f"{feature.canonical_domain} · {subdomains[0].title()}"
    return feature.canonical_domain


def build_cluster_metadata(members: list[StructuredFeature]) -> dict:
    location_counter = Counter(feature.location for feature in members if feature.location)
    subdomain_counter = Counter(sub for feature in members for sub in as_list(feature.subdomains))
    entity_counter = Counter(entity for feature in members for entity in as_list(feature.entities))
    item_type_counter = Counter(feature.item_type for feature in members if feature.item_type)
    intent_counter = Counter(feature.intent for feature in members if feature.intent)
    item_type_mode = item_type_counter.most_common(1)[0][0] if item_type_counter else ""
    primary_label = primary_subdomain([label for label, _ in subdomain_counter.most_common(5)], item_type_mode)
    top_location = ""
    if location_counter:
        top_location, top_count = location_counter.most_common(1)[0]
        if len(location_counter) > 1 and (top_count / max(len(members), 1)) < 0.6:
            top_location = ""
    if not should_scope_cluster_by_location(members[0].canonical_domain, [primary_label], item_type_mode):
        top_location = ""
    return {
        "canonical_domain": members[0].canonical_domain,
        "top_location": top_location,
        "top_subdomains": [label for label, _ in subdomain_counter.most_common(5)],
        "primary_subdomain": primary_label,
        "top_entities": [label for label, _ in entity_counter.most_common(6)],
        "item_type_mode": item_type_mode,
        "intent_mode": intent_counter.most_common(1)[0][0] if intent_counter else "",
        "member_reel_item_ids": [feature.reel_item_id for feature in members],
    }


def build_cluster_candidate_from_members(cluster_node_id: str, members: list[StructuredFeature]) -> ClusterCandidate:
    metadata = build_cluster_metadata(members)
    vectors = [feature.embedding_vector for feature in members if feature.embedding_vector]
    centroid = []
    if vectors:
        dims = len(vectors[0])
        centroid = [sum(vector[index] for vector in vectors) / len(vectors) for index in range(dims)]
    confidence = sum(
        max(
            feature.confidence_scores.get("domain", 0.0),
            feature.confidence_scores.get("subdomains", 0.0),
            feature.confidence_scores.get("location", 0.0),
        )
        for feature in members
    ) / max(len(members), 1)
    return ClusterCandidate(
        node_id=cluster_node_id,
        canonical_key="",
        display_hint="",
        confidence=confidence,
        save_count=len(members),
        recent_save_count=sum(1 for feature in members if feature.metadata.get("received_at_recency", 0.0) >= 0.4),
        growth_velocity=min(1.0, len(members) / 5.0),
        entropy=0.0,
        embedding_vector=centroid,
        metadata=metadata,
    )


def singleton_family_bucket(feature: StructuredFeature) -> str:
    label = primary_subdomain(feature.subdomains, feature.item_type)
    domain = feature.canonical_domain
    intent = feature.intent
    if not label or not intent:
        return ""

    if intent == "place_to_visit":
        if label in {"destinations", "travel planning", "cultural experience"}:
            return "travel_discovery"
        if label in PLACE_FOOD_LABELS:
            return f"food_places::{feature.location or 'mixed'}"
        if label in {"stay", "local rentals"}:
            return "stays_and_rentals"
        return "places"

    if intent == "recipe_to_make":
        return "recipes"

    if intent == "tool_to_use":
        return "apps_and_tools"

    if intent == "product_to_buy":
        if label in {"audio device", "kitchen device", "device", "consumer tech", "fitness accessories"}:
            return "tech_products"
        if label in {"fragrance", "beauty and style", "sneaker culture", "men's clothing brands"}:
            return "style_products"
        return "products"

    if intent == "media_to_watch_or_hear":
        if label == "music":
            return "music"
        return "screen_entertainment"

    if intent in {"idea_to_try", "advice_to_remember"}:
        if domain in {"Personal Growth", "Career & Money"}:
            return "advice_and_growth"
        if domain == "Lifestyle":
            return "lifestyle_ideas"
        return "ideas"

    return label


def singleton_family_signature(feature: StructuredFeature) -> tuple[str, str, str] | None:
    bucket = singleton_family_bucket(feature)
    if not bucket or not feature.intent:
        return None
    return (
        "" if cross_domain_family_bucket(bucket) else feature.canonical_domain,
        feature.intent,
        bucket,
    )


def cluster_family_bucket(members: list[StructuredFeature]) -> str:
    if not members:
        return ""
    sample = members[0]
    return singleton_family_bucket(sample)


def structural_split_label(feature: StructuredFeature) -> str:
    subdomains = as_list(feature.subdomains)
    if subdomains:
        return subdomains[0]
    return primary_subdomain(subdomains, feature.item_type)


def execute_structural_splits(
    repo: PersonalizationV2Repository,
    user_id: str,
    cluster_records: dict,
    assignments: list[dict],
    domain_nodes: dict,
) -> None:
    assignment_by_reel_item = {row["reel_item_id"]: row for row in assignments}
    original_clusters = list(cluster_records.items())
    for cluster_node_id, members in original_clusters:
        if not members or len(members) < 6:
            continue
        grouped = defaultdict(list)
        for feature in members:
            grouped[structural_split_label(feature)].append(feature)
        strong_groups = {label: group for label, group in grouped.items() if len(group) >= 2}
        if len(strong_groups) < 2:
            continue
        strong_total = sum(len(group) for group in strong_groups.values())
        if strong_total < len(members) - 1:
            continue

        ordered_groups = sorted(strong_groups.items(), key=lambda item: (-len(item[1]), item[0]))
        anchor_label, anchor_group = ordered_groups[0]
        cluster_records[cluster_node_id] = list(anchor_group)

        split_candidates = []
        for label, group in ordered_groups[1:]:
            representative = group[0]
            new_cluster_key = cluster_key_for_feature(representative)
            new_display_hint = cluster_display_hint(representative)
            new_cluster_node_id = repo.upsert_node(
                user_id=user_id,
                node_type="cluster",
                canonical_key=f"{new_cluster_key} :: split::{label}",
                display_hint=new_display_hint,
                parent_node_id=domain_nodes[representative.canonical_domain],
                metadata={
                    "canonical_domain": representative.canonical_domain,
                    "top_location": representative.location,
                    "top_subdomains": as_list(representative.subdomains)[:3],
                    "top_entities": as_list(representative.entities)[:5],
                    "item_type_mode": representative.item_type,
                    "intent_mode": representative.intent,
                    "split_from": cluster_node_id,
                },
                confidence=max(
                    representative.confidence_scores.get("domain", 0.0),
                    representative.confidence_scores.get("location", 0.0),
                    representative.confidence_scores.get("subdomains", 0.0),
                ),
                centroid_embedding_id=representative.embedding_id,
            )
            cluster_records[new_cluster_node_id] = list(group)
            split_candidates.append((label, new_cluster_node_id, group))
            for feature in group:
                assignment = assignment_by_reel_item.get(feature.reel_item_id)
                if assignment:
                    assignment["cluster_node_id"] = new_cluster_node_id
                    assignment["assignment_reason"] = {
                        "action": "split_structural_cluster",
                        "source_cluster_node_id": cluster_node_id,
                        "target_cluster_node_id": new_cluster_node_id,
                        "split_label": label,
                    }

        leftovers = [feature for label, group in grouped.items() if len(group) < 2 for feature in group]
        for feature in leftovers:
            best_target = cluster_node_id
            best_score = -1.0
            for candidate_node_id, candidate_members in [("anchor", anchor_group)] + [(node_id, group) for _, node_id, group in split_candidates]:
                compare_members = anchor_group if candidate_node_id == "anchor" else candidate_members
                candidate = build_cluster_candidate_from_members(
                    cluster_node_id if candidate_node_id == "anchor" else candidate_node_id,
                    compare_members,
                )
                score, _reasons = overlap_score(feature, candidate)
                if score > best_score:
                    best_score = score
                    best_target = cluster_node_id if candidate_node_id == "anchor" else candidate_node_id
            cluster_records[best_target].append(feature)
            assignment = assignment_by_reel_item.get(feature.reel_item_id)
            if assignment:
                assignment["cluster_node_id"] = best_target
                assignment["assignment_reason"] = {
                    "action": "split_structural_leftover_attach",
                    "source_cluster_node_id": cluster_node_id,
                    "target_cluster_node_id": best_target,
                    "split_label": structural_split_label(feature),
                }


def compact_singleton_families(cluster_records: dict, assignments: list[dict]) -> None:
    assignment_by_reel_item = {row["reel_item_id"]: row for row in assignments}
    grouped = defaultdict(list)
    for cluster_node_id, members in cluster_records.items():
        if len(members) != 1:
            continue
        feature = members[0]
        signature = singleton_family_signature(feature)
        if signature:
            grouped[signature].append((cluster_node_id, feature))

    for _signature, grouped_members in grouped.items():
        if len(grouped_members) < 2:
            continue
        anchor_node_id, _anchor_feature = grouped_members[0]
        for cluster_node_id, feature in grouped_members[1:]:
            cluster_records[anchor_node_id].append(feature)
            cluster_records[cluster_node_id] = []
            assignment = assignment_by_reel_item.get(feature.reel_item_id)
            if assignment:
                assignment["cluster_node_id"] = anchor_node_id
                assignment["assignment_reason"] = {
                    "action": "merge_singleton_family",
                    "source_cluster_node_id": cluster_node_id,
                    "target_cluster_node_id": anchor_node_id,
                    "canonical_domain": feature.canonical_domain,
                    "intent": feature.intent,
                    "primary_subdomain": primary_subdomain(feature.subdomains, feature.item_type),
                }


def merge_weak_cluster_families(cluster_records: dict, assignments: list[dict]) -> None:
    assignment_by_reel_item = {row["reel_item_id"]: row for row in assignments}
    grouped = defaultdict(list)
    for cluster_node_id, members in cluster_records.items():
        if not members:
            continue
        sample = members[0]
        family_bucket = cluster_family_bucket(members)
        if not family_bucket or not sample.intent:
            continue
        location_key = sample.location if family_bucket.startswith("food_places::") else ""
        domain_key = "" if cross_domain_family_bucket(family_bucket) else sample.canonical_domain
        grouped[(domain_key, sample.intent, family_bucket, location_key)].append((cluster_node_id, members))

    for _signature, entries in grouped.items():
        if len(entries) < 2:
            continue
        combined_size = sum(len(members) for _, members in entries)
        if combined_size > 8:
            continue
        anchor_node_id, anchor_members = entries[0]
        for cluster_node_id, members in entries[1:]:
            if cluster_node_id == anchor_node_id:
                continue
            for feature in members:
                anchor_members.append(feature)
                assignment = assignment_by_reel_item.get(feature.reel_item_id)
                if assignment:
                    assignment["cluster_node_id"] = anchor_node_id
                    assignment["assignment_reason"] = {
                        "action": "merge_weak_cluster_family",
                        "source_cluster_node_id": cluster_node_id,
                        "target_cluster_node_id": anchor_node_id,
                        "canonical_domain": feature.canonical_domain,
                        "intent": feature.intent,
                        "family_bucket": cluster_family_bucket(anchor_members),
                    }
            cluster_records[cluster_node_id] = []


def absorb_singletons(cluster_records: dict, assignments: list[dict]) -> None:
    assignment_by_reel_item = {row["reel_item_id"]: row for row in assignments}
    for cluster_node_id, members in list(cluster_records.items()):
        if len(members) != 1:
            continue
        feature = members[0]
        feature_bucket = singleton_family_bucket(feature)
        best_target = None
        best_score = 0.0
        best_reasons = {}
        best_threshold = 0.56
        for target_node_id, target_members in cluster_records.items():
            if target_node_id == cluster_node_id or len(target_members) < 2:
                continue
            candidate = build_cluster_candidate_from_members(target_node_id, target_members)
            score, reasons = overlap_score(feature, candidate)
            candidate_bucket = singleton_family_bucket(
                StructuredFeature(
                    reel_item_id="",
                    reel_id="",
                    user_id="",
                    primary_category="",
                    specific_category="",
                    item_name="",
                    summary="",
                    item_type=candidate.metadata.get("item_type_mode", ""),
                    canonical_domain=candidate.metadata.get("canonical_domain", ""),
                    subdomains=as_list(candidate.metadata.get("top_subdomains", [])),
                    entities=[],
                    location=candidate.metadata.get("top_location", ""),
                    vibe=[],
                    intent=candidate.metadata.get("intent_mode", ""),
                    audience_context="",
                    confidence_scores={},
                )
            )
            if feature_bucket.startswith("food_places::") and candidate_bucket.startswith("food_places::") and feature_bucket != candidate_bucket:
                continue
            family_bonus = 0.14 if feature_bucket and feature_bucket == candidate_bucket else 0.0
            intent_bonus = 0.08 if feature.intent and feature.intent == candidate.metadata.get("intent_mode", "") else 0.0
            threshold = 0.56
            if (
                feature_bucket
                and feature_bucket == candidate_bucket
                and feature.item_type in {"app", "product"}
            ):
                family_bonus += 0.06
                threshold = 0.48
            score += family_bonus + intent_bonus
            if score > best_score:
                best_target = target_node_id
                best_score = score
                best_threshold = threshold
                best_reasons = {
                    **reasons,
                    "singleton_family_bucket": feature_bucket,
                    "candidate_family_bucket": candidate_bucket,
                    "family_bonus": family_bonus,
                    "intent_bonus": intent_bonus,
                    "absorb_threshold": threshold,
                }
        if best_target and best_score >= best_threshold:
            cluster_records[best_target].append(feature)
            cluster_records[cluster_node_id] = []
            assignment = assignment_by_reel_item.get(feature.reel_item_id)
            if assignment:
                assignment["cluster_node_id"] = best_target
                assignment["assignment_score"] = max(float(assignment.get("assignment_score", 0.0)), best_score)
                assignment["assignment_reason"] = {
                    "action": "absorb_singleton",
                    "confidence": best_score,
                    "source_cluster_node_id": cluster_node_id,
                    "target_cluster_node_id": best_target,
                    **best_reasons,
                }


def title_for_cluster(metadata: dict, save_count: int, confidence: float) -> tuple[str, float]:
    location = metadata.get("top_location", "")
    subdomains = metadata.get("top_subdomains", [])
    item_type = metadata.get("item_type_mode", "")
    label = metadata.get("primary_subdomain") or primary_subdomain(subdomains, item_type)
    restaurant_family = PLACE_FOOD_LABELS - {"local food"}
    restaurant_labels = [value for value in subdomains if value in restaurant_family]
    if location and len(set(restaurant_labels)) >= 2 and save_count >= 3:
        return f"Restaurants in {location}", min(0.92, confidence + 0.06)
    if len(set(restaurant_labels)) >= 2 and save_count >= 2 and not location:
        return "Food Places", min(0.84, confidence + 0.04)
    if save_count >= 2 and "destinations" in subdomains and not location:
        return "Travel Destinations", min(0.86, confidence + 0.05)
    if save_count >= 2 and {"protein recipes", "recipes"} & set(subdomains):
        if "protein recipes" in subdomains and "recipes" in subdomains:
            return "Recipes", min(0.84, confidence + 0.04)
    if save_count >= 2 and {"app", "learning app", "job search tools"} & set(subdomains):
        return "Apps & Tools", min(0.86, confidence + 0.05)
    if save_count >= 2 and {"audio device", "kitchen device", "device", "fitness accessories"} & set(subdomains):
        return "Gadgets & Devices", min(0.86, confidence + 0.05)
    if save_count >= 2 and {"job search tools", "wealth education", "money making ideas", "startup advice"} & set(subdomains):
        return "Career Growth", min(0.82, confidence + 0.04)
    if location and label and save_count >= 2 and confidence >= 0.58:
        if label in {"restaurant", "restaurants"}:
            return f"Restaurants in {location}", min(0.94, confidence + 0.08)
        if label == "seafood restaurants":
            return f"Seafood Restaurants in {location}", min(0.94, confidence + 0.08)
        if label == "street food":
            return f"Street Food in {location}", min(0.94, confidence + 0.08)
        if label == "cafes":
            return f"Cafes in {location}", min(0.92, confidence + 0.06)
        if label == "late-night food":
            return f"Late-Night Food in {location}", min(0.90, confidence + 0.05)
        if label == "recipe":
            return f"{location} Recipes", min(0.88, confidence + 0.04)
        if label == "stay":
            return f"{location} Stay", min(0.90, confidence + 0.05)
        if label == "destinations":
            return location, min(0.90, confidence + 0.05)
        return f"{location} {label.title()}", min(0.9, confidence + 0.05)
    if location and label == "destinations":
        return location, min(0.88, confidence + 0.04)
    if location and save_count >= 3 and confidence >= 0.6:
        return location, min(0.9, confidence + 0.06)
    if label and save_count >= 2:
        return title_override_for_subdomain(label), min(0.86, confidence + 0.05)
    if label and confidence >= 0.72:
        return title_override_for_subdomain(label), min(0.82, confidence + 0.04)
    if item_type and save_count >= 2:
        if item_type == "product":
            return "Useful Products", min(0.80, confidence + 0.03)
        if item_type == "media":
            return "Entertainment", min(0.78, confidence + 0.02)
        return f"{item_type.title()} Picks", min(0.78, confidence + 0.02)
    return metadata.get("canonical_domain", "General Picks"), max(0.45, confidence)


def rebuild_user_graph(repo: PersonalizationV2Repository, user_id: str) -> dict:
    features = repo.load_features(user_id)
    repo.reset_user_graph(user_id)

    domain_nodes = {}
    location_nodes = {}
    subdomain_nodes = {}
    cluster_records = {}
    cluster_analysis = {}
    assignments = []
    edges = []
    cluster_titles = []

    for feature in features:
        domain_node_id = domain_nodes.get(feature.canonical_domain)
        if not domain_node_id:
            domain_node_id = repo.upsert_node(
                user_id=user_id,
                node_type="domain",
                canonical_key=feature.canonical_domain,
                display_hint=feature.canonical_domain,
                metadata={"canonical_domain": feature.canonical_domain},
                confidence=feature.confidence_scores.get("domain", 0.0),
            )
            domain_nodes[feature.canonical_domain] = domain_node_id

        if feature.location and feature.location not in location_nodes:
            location_nodes[feature.location] = repo.upsert_node(
                user_id=user_id,
                node_type="location",
                canonical_key=feature.location,
                display_hint=feature.location,
                parent_node_id=domain_node_id,
                metadata={"location": feature.location, "canonical_domain": feature.canonical_domain},
                confidence=feature.confidence_scores.get("location", 0.0),
            )
            edges.append(
                {
                    "from_node_id": domain_node_id,
                    "to_node_id": location_nodes[feature.location],
                    "edge_type": "contains_location",
                    "weight": 1.0,
                    "evidence_count": 1,
                    "metadata": {"canonical_domain": feature.canonical_domain},
                }
            )

        for subdomain in feature.subdomains:
            subdomain = str(subdomain).strip()
            if not subdomain:
                continue
            if subdomain not in subdomain_nodes:
                subdomain_nodes[subdomain] = repo.upsert_node(
                    user_id=user_id,
                    node_type="subdomain",
                    canonical_key=subdomain,
                    display_hint=subdomain.title(),
                    parent_node_id=domain_node_id,
                    metadata={"subdomain": subdomain, "canonical_domain": feature.canonical_domain},
                    confidence=feature.confidence_scores.get("subdomains", 0.0),
                )
                edges.append(
                    {
                        "from_node_id": domain_node_id,
                        "to_node_id": subdomain_nodes[subdomain],
                        "edge_type": "contains_subdomain",
                        "weight": 1.0,
                        "evidence_count": 1,
                        "metadata": {"canonical_domain": feature.canonical_domain},
                    }
                )

    cluster_candidates = []
    for feature in features:
        if not feature.embedding_vector:
            vector, model = embed_text(feature_embedding_text(feature))
            embedding_id = repo.upsert_embedding(
                object_type="reel_item_feature",
                object_id=str(feature.reel_item_id),
                model=model,
                version=ASSIGNMENT_VERSION,
                vector=vector,
                source_text_hash=stable_hash(feature_embedding_text(feature)),
            )
            feature.embedding_vector = vector
            feature.embedding_id = embedding_id
            repo.upsert_feature(feature)

        best_candidate = None
        best_score = 0.0
        best_reasons = {}
        for candidate in cluster_candidates:
            score, reasons = overlap_score(feature, candidate)
            if score > best_score:
                best_score = score
                best_candidate = candidate
                best_reasons = reasons

        threshold = 0.62 if feature.location else 0.67
        if best_candidate and best_score >= threshold:
            decision = AssignmentDecision(
                cluster_node_id=best_candidate.node_id,
                cluster_key=best_candidate.canonical_key,
                assignment_score=best_score,
                confidence=max(best_candidate.confidence, best_score),
                action="attach_existing_cluster",
                reasons=best_reasons,
            )
        else:
            cluster_key = cluster_key_for_feature(feature)
            display_hint = cluster_display_hint(feature)
            cluster_node_id = repo.upsert_node(
                user_id=user_id,
                node_type="cluster",
                canonical_key=cluster_key,
                display_hint=display_hint,
                parent_node_id=domain_nodes[feature.canonical_domain],
                metadata={
                    "canonical_domain": feature.canonical_domain,
                    "top_location": feature.location,
                    "top_subdomains": as_list(feature.subdomains)[:3],
                    "top_entities": as_list(feature.entities)[:5],
                    "item_type_mode": feature.item_type,
                    "intent_mode": feature.intent,
                },
                confidence=max(
                    feature.confidence_scores.get("domain", 0.0),
                    feature.confidence_scores.get("location", 0.0),
                    feature.confidence_scores.get("subdomains", 0.0),
                ),
                centroid_embedding_id=feature.embedding_id,
            )
            candidate = ClusterCandidate(
                node_id=cluster_node_id,
                canonical_key=cluster_key,
                display_hint=display_hint,
                confidence=max(
                    feature.confidence_scores.get("domain", 0.0),
                    feature.confidence_scores.get("location", 0.0),
                    feature.confidence_scores.get("subdomains", 0.0),
                ),
                save_count=0,
                recent_save_count=0,
                growth_velocity=0.0,
                entropy=0.0,
                embedding_vector=feature.embedding_vector,
                metadata={
                    "canonical_domain": feature.canonical_domain,
                    "top_location": feature.location,
                    "top_subdomains": as_list(feature.subdomains)[:3],
                    "top_entities": as_list(feature.entities)[:5],
                    "item_type_mode": feature.item_type,
                    "intent_mode": feature.intent,
                },
            )
            cluster_candidates.append(candidate)
            decision = AssignmentDecision(
                cluster_node_id=cluster_node_id,
                cluster_key=cluster_key,
                assignment_score=1.0,
                confidence=candidate.confidence,
                action="create_cluster",
                reasons={
                    "cluster_key": cluster_key,
                    "threshold": threshold,
                    "location": feature.location,
                    "subdomains": as_list(feature.subdomains),
                },
            )

        assignments.append(
            {
                "reel_item_id": feature.reel_item_id,
                "cluster_node_id": decision.cluster_node_id,
                "assignment_score": decision.assignment_score,
                "assignment_reason": {
                    "action": decision.action,
                    "cluster_key": decision.cluster_key,
                    "confidence": decision.confidence,
                    **decision.reasons,
                },
                "assignment_version": ASSIGNMENT_VERSION,
            }
        )

        cluster_records.setdefault(decision.cluster_node_id, []).append(feature)

    compact_singleton_families(cluster_records, assignments)
    merge_weak_cluster_families(cluster_records, assignments)
    absorb_singletons(cluster_records, assignments)
    execute_structural_splits(repo, user_id, cluster_records, assignments, domain_nodes)
    absorb_singletons(cluster_records, assignments)
    repo.replace_cluster_memberships(user_id, assignments)

    for cluster_node_id, members in cluster_records.items():
        if not members:
            continue
        location_counter = Counter(feature.location for feature in members if feature.location)
        subdomain_counter = Counter(sub for feature in members for sub in as_list(feature.subdomains))
        entity_counter = Counter(entity for feature in members for entity in as_list(feature.entities))
        item_type_counter = Counter(feature.item_type for feature in members if feature.item_type)
        intent_counter = Counter(feature.intent for feature in members if feature.intent)
        confidence = sum(
            max(
                feature.confidence_scores.get("domain", 0.0),
                feature.confidence_scores.get("subdomains", 0.0),
                feature.confidence_scores.get("location", 0.0),
            )
            for feature in members
        ) / max(len(members), 1)
        recent_count = sum(1 for feature in members if feature.metadata.get("received_at_recency", 0.0) >= 0.4)
        vectors = [feature.embedding_vector for feature in members if feature.embedding_vector]
        centroid = []
        if vectors:
            dims = len(vectors[0])
            centroid = [
                sum(vector[index] for vector in vectors) / len(vectors)
                for index in range(dims)
            ]
        embedding_id = None
        if centroid:
            embedding_id = repo.upsert_embedding(
                object_type="cluster",
                object_id=cluster_node_id,
                model="derived-centroid",
                version=ASSIGNMENT_VERSION,
                vector=centroid,
                source_text_hash=stable_hash(cluster_node_id + str(len(members))),
            )

        proportions = [count / len(members) for count in subdomain_counter.values()] or [1.0]
        entropy = -sum(p * math.log(p, 2) for p in proportions if p > 0)
        growth_velocity = min(1.0, len(members) / 5.0)
        metadata = build_cluster_metadata(members)
        repo.update_node_metrics(
            cluster_node_id,
            {
                "save_count": len(members),
                "recent_save_count": recent_count,
                "growth_velocity": growth_velocity,
                "entropy": entropy,
                "confidence": confidence,
                "centroid_embedding_id": embedding_id,
                "metadata": metadata,
            },
        )
        split_score, split_components = split_score_for_cluster(len(members), metadata, growth_velocity, entropy)
        cluster_analysis[cluster_node_id] = {
            "cluster_node_id": cluster_node_id,
            "save_count": len(members),
            "recent_save_count": recent_count,
            "growth_velocity": growth_velocity,
            "entropy": entropy,
            "confidence": confidence,
            "centroid_embedding_id": embedding_id,
            "metadata": metadata,
            "embedding_vector": centroid,
            "split_score": split_score,
            "split_components": split_components,
        }
        title, title_confidence = title_for_cluster(metadata, len(members), confidence)
        cluster_titles.append(
            {
                "cluster_node_id": cluster_node_id,
                "title": title,
                "title_confidence": title_confidence,
                "generation_reason": {
                    "location": metadata.get("top_location", ""),
                    "top_subdomains": metadata.get("top_subdomains", []),
                    "save_count": len(members),
                    "confidence": confidence,
                },
            }
        )
        repo.create_cluster_event(
            user_id=user_id,
            cluster_node_id=cluster_node_id,
            event_type="cluster_stabilized",
            reason={
                "save_count": len(members),
                "recent_save_count": recent_count,
                "entropy": entropy,
                "confidence": confidence,
            },
        )

        if metadata.get("top_location"):
            edges.append(
                {
                    "from_node_id": cluster_node_id,
                    "to_node_id": location_nodes[metadata["top_location"]],
                    "edge_type": "supports_location",
                    "weight": len(members),
                    "evidence_count": len(members),
                    "metadata": {"confidence": confidence},
                }
            )
        for subdomain in metadata.get("top_subdomains", []):
            if subdomain in subdomain_nodes:
                edges.append(
                    {
                        "from_node_id": cluster_node_id,
                        "to_node_id": subdomain_nodes[subdomain],
                        "edge_type": "supports_subdomain",
                        "weight": subdomain_counter[subdomain],
                        "evidence_count": subdomain_counter[subdomain],
                        "metadata": {"confidence": confidence},
                    }
                )

    for analysis in cluster_analysis.values():
        if analysis["split_score"] >= 0.68 and analysis["save_count"] >= 4:
            repo.create_cluster_event(
                user_id=user_id,
                cluster_node_id=analysis["cluster_node_id"],
                event_type="split_candidate",
                reason={
                    "split_score": analysis["split_score"],
                    "components": analysis["split_components"],
                    "top_subdomains": analysis["metadata"].get("top_subdomains", []),
                    "top_location": analysis["metadata"].get("top_location", ""),
                },
            )
            analysis["metadata"]["proposed_action"] = "split_candidate"
            analysis["metadata"]["split_score"] = analysis["split_score"]
            repo.update_node_metrics(
                analysis["cluster_node_id"],
                {
                    "save_count": analysis["save_count"],
                    "recent_save_count": analysis["recent_save_count"],
                    "growth_velocity": analysis["growth_velocity"],
                    "entropy": analysis["entropy"],
                    "confidence": analysis["confidence"],
                    "centroid_embedding_id": analysis["centroid_embedding_id"],
                    "metadata": analysis["metadata"],
                },
            )

    cluster_analysis_rows = list(cluster_analysis.values())
    for index, left in enumerate(cluster_analysis_rows):
        for right in cluster_analysis_rows[index + 1:]:
            merge_score, merge_components = merge_score_between_clusters(left, right)
            if merge_score >= 0.72:
                repo.create_cluster_event(
                    user_id=user_id,
                    cluster_node_id=left["cluster_node_id"],
                    event_type="merge_candidate",
                    source_ids=[left["cluster_node_id"], right["cluster_node_id"]],
                    reason={
                        "merge_score": merge_score,
                        "components": merge_components,
                    },
                    target_ids=[],
                )

    repo.replace_edges(user_id, edges)
    repo.replace_cluster_titles(cluster_titles)
    return repo.load_debug_snapshot(user_id)
