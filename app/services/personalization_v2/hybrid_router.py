from __future__ import annotations

import json
import math
import time
from collections import Counter, defaultdict

from api_config import get_openai_client
from app.services.personalization_v2.graph_engine import (
    ASSIGNMENT_VERSION,
    as_list,
    build_cluster_metadata,
    stable_hash,
)
from app.services.personalization_v2.models import StructuredFeature
from app.services.personalization_v2.repository import PersonalizationV2Repository


ROUTER_MODEL = "gpt-4.1"
HYBRID_ASSIGNMENT_VERSION = "v2-llm-hybrid"
STABLE_LIST_MIN_SIZE = 5
LOW_CONFIDENCE_ASSIGNMENT_SCORE = 0.72


def normalize(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def compact_list_descriptor(row: dict) -> dict:
    return {
        "title": row["title"],
        "domain": row["canonical_domain"],
        "location": row["top_location"],
        "subdomains": row["top_subdomains"][:4],
        "intent": row["intent_mode"],
        "item_type": row["item_type_mode"],
        "item_count": row["item_count"],
        "sample_items": row["sample_items"][:5],
        "sample_categories": row["sample_categories"][:3],
    }


def compact_item(row: dict) -> dict:
    return {
        "reel_item_id": row["reel_item_id"],
        "item_name": row["item_name"],
        "summary": row["summary"],
        "primary_category": row["primary_category"],
        "specific_category": row["specific_category"],
        "canonical_domain": row["canonical_domain"],
        "canonical_subdomains": row["canonical_subdomains"],
        "canonical_location": row["canonical_location"],
        "item_type": row["item_type"],
        "intent": row["intent"],
        "product_name": row["product_name"],
        "product_type": row["product_type"],
        "product_brand": row["product_brand"],
        "contains_product": row["contains_product"],
        "url": row["url"],
        "current_list_title": row["current_list_title"],
    }


def build_router_prompt(existing_lists: list[dict], items_to_route: list[dict]) -> str:
    instructions = """
You are the routing brain for a saved-reel organizer.

You are given:
1. an existing set of list titles that already organize one user's saved reels
2. a smaller set of items that look weak, uncertain, or newly introduced

Your job:
- choose the best existing list for each item whenever a natural fit exists
- create a new list only if none of the existing lists fits well enough

Think like a careful human organizer, not like a keyword matcher.

Important:
- Strong existing lists are already useful. Do not create a new list unless it is clearly better.
- Prefer stable, reusable list titles over narrow temporary phrasing.
- If an item already has a reasonable current list, keep it there unless another list is clearly better.

Decision rules:
- Location-specific food venues, cafes, dessert spots, and restaurants should go into a matching city list if one exists.
- Apps, AI products, websites, software tools, or services people use should go into an app/tool list rather than a vague education or general list.
- Recipes, meal prep ideas, and dishes to cook should go into a recipe list even if a gadget like an air fryer or blender is mentioned.
- Songs, dance moves, dance tutorials, artist recommendations, and music discovery should prefer music-style lists unless the item is clearly a film or show.
- Fashion, styling, appearance tips, grooming, hair, and visual self-presentation should prefer Beauty & Style over clothing-brand lists unless the reel is mainly about specific brands.
- Clothing color theory, personal color palette advice, attractiveness-by-color, and general appearance improvement tips should prefer Beauty & Style, not Men's Clothing Brands, unless specific brands are the main thing being saved.
- Products should be routed by the main thing being saved. Side commentary should not override the concrete product, app, place, or media item.
- Use "Needs Review" only when the item is truly too empty or ambiguous to place confidently.

Return strict JSON:
{
  "assignments": [
    {
      "reel_item_id": 123,
      "decision": "assign_existing" | "create_new",
      "list_title": "exact existing title or exact new title",
      "confidence": 0.0,
      "reason": "short explanation"
    }
  ]
}

Rules:
- Every reel_item_id must appear exactly once.
- If decision is "assign_existing", list_title must exactly match one of the existing titles.
- If decision is "create_new", list_title must be a new human-readable list title.
- Confidence must be between 0 and 1.
""".strip()
    payload = {
        "existing_lists": [compact_list_descriptor(row) for row in existing_lists],
        "items_to_route": [compact_item(row) for row in items_to_route],
    }
    return f"{instructions}\n\nINPUT\n{json.dumps(payload, ensure_ascii=False, indent=2)}"


def call_router(prompt: str) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            client = get_openai_client()
            response = client.chat.completions.create(
                model=ROUTER_MODEL,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(response.choices[0].message.content)
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(0.8 * attempt)
    raise last_error or RuntimeError("Hybrid router call failed")


def chunked(values: list[dict], size: int) -> list[list[dict]]:
    return [values[index:index + size] for index in range(0, len(values), size)]


def build_seed_lists(snapshot: dict) -> tuple[list[dict], dict[int, str], dict[str, list[int]], dict[int, float]]:
    titles_by_cluster = {row["cluster_node_id"]: normalize(row.get("title")) for row in snapshot.get("titles", [])}
    features_by_id = {int(row["reel_item_id"]): row for row in snapshot.get("features", [])}
    members_by_cluster: dict[str, list[int]] = defaultdict(list)
    assignment_scores: dict[int, float] = {}
    seed_assignments: dict[int, str] = {}

    for membership in snapshot.get("memberships", []):
        reel_item_id = int(membership["reel_item_id"])
        cluster_id = membership["cluster_node_id"]
        members_by_cluster[cluster_id].append(reel_item_id)
        assignment_scores[reel_item_id] = float(membership.get("assignment_score", 0.0) or 0.0)

    clusters = [
        row
        for row in snapshot.get("nodes", [])
        if row.get("node_type") == "cluster" and int(row.get("save_count", 0) or 0) > 0
    ]
    clusters.sort(key=lambda row: (-int(row.get("save_count", 0) or 0), titles_by_cluster.get(row["id"], "")))

    seed_lists = []
    for cluster in clusters:
        title = titles_by_cluster.get(cluster["id"]) or normalize(cluster.get("display_hint")) or "Untitled List"
        metadata = cluster.get("metadata_json") or {}
        member_ids = members_by_cluster.get(cluster["id"], [])
        sample_items = []
        sample_categories = []
        for reel_item_id in member_ids:
            seed_assignments[reel_item_id] = title
            feature = features_by_id.get(reel_item_id)
            if not feature:
                continue
            item_name = normalize(feature.get("item_name"))
            specific_category = normalize(feature.get("specific_category"))
            if item_name and len(sample_items) < 6:
                sample_items.append(item_name)
            if specific_category and specific_category not in sample_categories and len(sample_categories) < 4:
                sample_categories.append(specific_category)
        seed_lists.append(
            {
                "title": title,
                "item_count": int(cluster.get("save_count", 0) or 0),
                "canonical_domain": normalize(metadata.get("canonical_domain")),
                "top_location": normalize(metadata.get("top_location")),
                "top_subdomains": [normalize(value) for value in (metadata.get("top_subdomains") or []) if normalize(value)],
                "intent_mode": normalize(metadata.get("intent_mode")),
                "item_type_mode": normalize(metadata.get("item_type_mode")),
                "sample_items": sample_items,
                "sample_categories": sample_categories,
            }
        )
    members_by_title = {
        row["title"]: [reel_item_id for reel_item_id, title in seed_assignments.items() if title == row["title"]]
        for row in seed_lists
    }
    return seed_lists, seed_assignments, members_by_title, assignment_scores


def build_router_items(
    features: list[StructuredFeature],
    reel_items_by_id: dict[int, object],
    seed_assignments: dict[int, str],
) -> list[dict]:
    rows = []
    for feature in features:
        reel_item = reel_items_by_id.get(feature.reel_item_id)
        rows.append(
            {
                "reel_item_id": feature.reel_item_id,
                "reel_id": feature.reel_id,
                "url": normalize(getattr(reel_item, "url", "")),
                "primary_category": feature.primary_category,
                "specific_category": feature.specific_category,
                "item_name": feature.item_name,
                "summary": feature.summary,
                "canonical_domain": feature.canonical_domain,
                "canonical_subdomains": as_list(feature.subdomains),
                "canonical_location": feature.location,
                "item_type": feature.item_type,
                "intent": feature.intent,
                "product_name": normalize(getattr(reel_item, "product_name", "")),
                "product_type": normalize(getattr(reel_item, "product_type", "")),
                "product_brand": normalize(getattr(reel_item, "brand", "")),
                "contains_product": "yes" if normalize(getattr(reel_item, "product_name", "")) else "no",
                "current_list_title": seed_assignments.get(feature.reel_item_id, ""),
            }
        )
    rows.sort(key=lambda row: row["reel_item_id"])
    return rows


def split_seed_lists(seed_lists: list[dict]) -> tuple[set[str], set[str]]:
    stable = set()
    weak = set()
    for row in seed_lists:
        title = row["title"]
        if title == "Needs Review":
            weak.add(title)
            continue
        if row["item_count"] >= STABLE_LIST_MIN_SIZE:
            stable.add(title)
        else:
            weak.add(title)
    return stable, weak


def choose_router_candidates(
    router_items: list[dict],
    stable_titles: set[str],
    assignment_scores: dict[int, float],
) -> list[dict]:
    def should_escape_stable_list(item: dict) -> bool:
        current_title = item["current_list_title"]
        subdomains = set(item["canonical_subdomains"])
        specific = normalize(item["specific_category"]).lower()
        item_name = normalize(item["item_name"]).lower()
        summary = normalize(item["summary"]).lower()
        text_blob = " ".join(part for part in [specific, item_name, summary] if part)

        if item["intent"] == "recipe_to_make" and current_title != "Recipes":
            return True
        if item["intent"] == "tool_to_use" and current_title != "Apps & Tools":
            return True
        if "beauty and style" in subdomains and current_title == "Men's Clothing Brands":
            return True
        if current_title == "Films & Shows" and any(token in text_blob for token in ["dance", "shuffle", "footwork", "cha cha", "social function"]):
            return True
        if current_title == "Gadgets & Devices" and item["intent"] == "recipe_to_make":
            return True
        return False

    candidates = []
    for item in router_items:
        current_title = item["current_list_title"]
        score = assignment_scores.get(item["reel_item_id"], 0.0)
        if current_title not in stable_titles or score < LOW_CONFIDENCE_ASSIGNMENT_SCORE or should_escape_stable_list(item):
            candidates.append(item)
    return candidates


def route_candidates(seed_lists: list[dict], candidate_items: list[dict], batch_size: int = 8) -> tuple[list[dict], list[dict]]:
    allowed_titles = {row["title"] for row in seed_lists}
    dynamic_lists = [dict(row) for row in seed_lists]
    assignments = []
    debug_rows = []

    for batch_index, batch in enumerate(chunked(candidate_items, batch_size), start=1):
        prompt = build_router_prompt(dynamic_lists, batch)
        response = call_router(prompt)
        returned = {int(row["reel_item_id"]): row for row in response.get("assignments", []) if str(row.get("reel_item_id", "")).strip()}

        for item in batch:
            row = returned.get(item["reel_item_id"], {})
            decision = normalize(row.get("decision")).lower() or "assign_existing"
            title = normalize(row.get("list_title")) or item["current_list_title"] or "Needs Review"
            reason = normalize(row.get("reason")) or "hybrid_router_fallback"
            try:
                confidence = float(row.get("confidence", 0.0) or 0.0)
            except Exception:
                confidence = 0.0

            if decision == "assign_existing" and title not in allowed_titles:
                title = item["current_list_title"] if item["current_list_title"] in allowed_titles else "Needs Review"
                confidence = min(confidence, 0.35)
                reason = f"{reason} | invalid_existing_title_fallback"

            if decision == "create_new" and title in allowed_titles:
                decision = "assign_existing"
                reason = f"{reason} | promoted_to_existing"

            if decision == "create_new" and title not in allowed_titles:
                allowed_titles.add(title)
                dynamic_lists.append(
                    {
                        "title": title,
                        "item_count": 0,
                        "canonical_domain": item["canonical_domain"],
                        "top_location": item["canonical_location"],
                        "top_subdomains": item["canonical_subdomains"][:4],
                        "intent_mode": item["intent"],
                        "item_type_mode": item["item_type"],
                        "sample_items": [],
                        "sample_categories": [],
                    }
                )

            assignments.append(
                {
                    "reel_item_id": item["reel_item_id"],
                    "decision": decision,
                    "list_title": title,
                    "confidence": round(confidence, 4),
                    "reason": reason,
                }
            )
        debug_rows.append({"batch_index": batch_index, "prompt": prompt, "response": response})
    return assignments, debug_rows


def build_final_collections(
    seed_lists: list[dict],
    stable_titles: set[str],
    router_items: list[dict],
    router_assignments: list[dict],
) -> tuple[list[dict], dict[int, dict]]:
    items_by_id = {row["reel_item_id"]: row for row in router_items}
    reassigned_ids = {row["reel_item_id"] for row in router_assignments}
    assignment_by_id = {row["reel_item_id"]: row for row in router_assignments}
    collections: dict[str, list[dict]] = defaultdict(list)

    for item in router_items:
        current_title = item["current_list_title"]
        if item["reel_item_id"] not in reassigned_ids:
            collections[current_title].append(item)

    for assignment in router_assignments:
        item = items_by_id[assignment["reel_item_id"]]
        collections[assignment["list_title"]].append({**item, "router_assignment": assignment})

    collection_rows = []
    assignment_metadata: dict[int, dict] = {}
    seed_lookup = {row["title"]: row for row in seed_lists}
    for title, members in collections.items():
        if not members:
            continue
        members.sort(key=lambda row: (row["canonical_location"], row["item_name"].lower(), row["reel_item_id"]))
        domain_counter = Counter(row["canonical_domain"] for row in members if row["canonical_domain"])
        location_counter = Counter(row["canonical_location"] for row in members if row["canonical_location"])
        intent_counter = Counter(row["intent"] for row in members if row["intent"])
        item_type_counter = Counter(row["item_type"] for row in members if row["item_type"])
        subdomain_counter = Counter()
        for row in members:
            subdomain_counter.update(row["canonical_subdomains"])
        collection_rows.append(
            {
                "list_title": title,
                "item_count": len(members),
                "canonical_domain": domain_counter.most_common(1)[0][0] if domain_counter else seed_lookup.get(title, {}).get("canonical_domain", ""),
                "top_location": location_counter.most_common(1)[0][0] if location_counter else seed_lookup.get(title, {}).get("top_location", ""),
                "intent_mode": intent_counter.most_common(1)[0][0] if intent_counter else seed_lookup.get(title, {}).get("intent_mode", ""),
                "item_type_mode": item_type_counter.most_common(1)[0][0] if item_type_counter else seed_lookup.get(title, {}).get("item_type_mode", ""),
                "top_subdomains": [value for value, _ in subdomain_counter.most_common(5)],
                "items": members,
                "is_stable_seed": title in stable_titles,
            }
        )
        for row in members:
            assignment = row.get("router_assignment") or {}
            assignment_metadata[row["reel_item_id"]] = {
                "list_title": title,
                "confidence": float(assignment.get("confidence", 0.88 if title in stable_titles else 0.74) or 0.0),
                "reason": assignment.get("reason", "kept_stable_seed_list" if title in stable_titles else "kept_seed_list"),
                "decision": assignment.get("decision", "kept_seed_list"),
                "seed_list_title": row["current_list_title"],
            }
    collection_rows.sort(key=lambda row: (-row["item_count"], row["list_title"].lower()))
    return collection_rows, assignment_metadata


def persist_hybrid_snapshot(
    repo: PersonalizationV2Repository,
    user_id: str,
    features: list[StructuredFeature],
    collections: list[dict],
    assignment_metadata: dict[int, dict],
) -> dict:
    repo.reset_user_graph(user_id)
    domain_nodes = {}
    cluster_titles = []
    assignments = []
    edges: list[dict] = []
    feature_by_id = {feature.reel_item_id: feature for feature in features}

    for collection in collections:
        domain = collection["canonical_domain"] or "Personalized"
        if domain not in domain_nodes:
            domain_nodes[domain] = repo.upsert_node(
                user_id=user_id,
                node_type="domain",
                canonical_key=domain,
                display_hint=domain,
                metadata={"canonical_domain": domain, "source": "hybrid_router"},
                confidence=0.82,
            )

    for collection in collections:
        domain = collection["canonical_domain"] or "Personalized"
        members = [feature_by_id[row["reel_item_id"]] for row in collection["items"] if row["reel_item_id"] in feature_by_id]
        if not members:
            continue
        metadata = build_cluster_metadata(members)
        metadata.update(
            {
                "source": "hybrid_router",
                "stable_seed_list": bool(collection.get("is_stable_seed")),
                "router_list_title": collection["list_title"],
            }
        )
        cluster_node_id = repo.upsert_node(
            user_id=user_id,
            node_type="cluster",
            canonical_key=f"{domain} :: {collection['list_title']}",
            display_hint=collection["list_title"],
            parent_node_id=domain_nodes[domain],
            metadata=metadata,
            confidence=0.86,
            centroid_embedding_id=None,
        )

        vectors = [feature.embedding_vector for feature in members if feature.embedding_vector]
        centroid = []
        if vectors:
            dims = len(vectors[0])
            centroid = [sum(vector[index] for vector in vectors) / len(vectors) for index in range(dims)]
        embedding_id = None
        if centroid:
            embedding_id = repo.upsert_embedding(
                object_type="cluster",
                object_id=cluster_node_id,
                model="derived-centroid",
                version=HYBRID_ASSIGNMENT_VERSION,
                vector=centroid,
                source_text_hash=stable_hash(cluster_node_id + str(len(members))),
            )

        subdomain_counter = Counter(sub for feature in members for sub in as_list(feature.subdomains))
        proportions = [count / len(members) for count in subdomain_counter.values()] or [1.0]
        entropy = -sum(p * math.log(p, 2) for p in proportions if p > 0)
        confidence = sum(
            assignment_metadata[feature.reel_item_id]["confidence"]
            for feature in members
            if feature.reel_item_id in assignment_metadata
        ) / max(len(members), 1)
        repo.update_node_metrics(
            cluster_node_id,
            {
                "save_count": len(members),
                "recent_save_count": 0,
                "growth_velocity": min(1.0, len(members) / 5.0),
                "entropy": entropy,
                "confidence": confidence,
                "centroid_embedding_id": embedding_id,
                "metadata": metadata,
            },
        )

        cluster_titles.append(
            {
                "cluster_node_id": cluster_node_id,
                "title": collection["list_title"],
                "title_confidence": confidence,
                "generation_reason": {
                    "source": "hybrid_router",
                    "stable_seed_list": bool(collection.get("is_stable_seed")),
                    "top_location": collection.get("top_location", ""),
                    "top_subdomains": collection.get("top_subdomains", []),
                    "item_count": len(members),
                },
            }
        )

        for feature in members:
            meta = assignment_metadata.get(feature.reel_item_id, {})
            assignments.append(
                {
                    "reel_item_id": feature.reel_item_id,
                    "cluster_node_id": cluster_node_id,
                    "assignment_score": meta.get("confidence", 0.8),
                    "assignment_reason": {
                        "action": "hybrid_router_assignment",
                        "list_title": collection["list_title"],
                        "decision": meta.get("decision", "kept_seed_list"),
                        "reason": meta.get("reason", ""),
                        "seed_list_title": meta.get("seed_list_title", ""),
                    },
                    "assignment_version": HYBRID_ASSIGNMENT_VERSION,
                }
            )

    repo.replace_edges(user_id, edges)
    repo.replace_cluster_memberships(user_id, assignments)
    repo.replace_cluster_titles(cluster_titles)
    return repo.load_debug_snapshot(user_id)


def improve_snapshot_with_hybrid_router(
    repo: PersonalizationV2Repository,
    user_id: str,
    seed_snapshot: dict,
    batch_size: int = 8,
) -> dict:
    seed_lists, seed_assignments, _members_by_title, assignment_scores = build_seed_lists(seed_snapshot)
    stable_titles, _weak_titles = split_seed_lists(seed_lists)

    reel_items = repo.load_reel_items(user_id)
    reel_items_by_id = {item.reel_item_id: item for item in reel_items}
    features = repo.load_features(user_id)
    router_items = build_router_items(features, reel_items_by_id, seed_assignments)
    candidates = choose_router_candidates(router_items, stable_titles, assignment_scores)
    if not candidates:
        return seed_snapshot

    router_assignments, _debug_rows = route_candidates(seed_lists, candidates, batch_size=batch_size)
    collections, assignment_metadata = build_final_collections(seed_lists, stable_titles, router_items, router_assignments)
    return persist_hybrid_snapshot(repo, user_id, features, collections, assignment_metadata)
