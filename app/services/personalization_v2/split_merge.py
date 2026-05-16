from __future__ import annotations

from collections import Counter

from app.services.personalization_v2.embeddings import cosine_similarity


def split_score_for_cluster(member_count: int, metadata: dict, growth_velocity: float, entropy: float) -> tuple[float, dict]:
    subdomains = metadata.get("top_subdomains", [])
    top_entities = metadata.get("top_entities", [])
    semantic_density = min(member_count / 6.0, 1.0)
    save_frequency = min(member_count / 5.0, 1.0)
    co_occurrence = 1.0 if metadata.get("top_location") and len(subdomains) >= 2 else 0.45 if metadata.get("top_location") else 0.25
    entity_overlap = min(len(top_entities) / max(member_count, 1), 1.0)
    temporal_growth = min(growth_velocity, 1.0)
    score = (
        semantic_density * 0.25 +
        save_frequency * 0.20 +
        co_occurrence * 0.20 +
        entity_overlap * 0.20 +
        temporal_growth * 0.15
    )
    return score, {
        "semantic_density": semantic_density,
        "save_frequency": save_frequency,
        "co_occurrence": co_occurrence,
        "entity_overlap": entity_overlap,
        "temporal_growth": temporal_growth,
        "entropy": entropy,
    }


def merge_score_between_clusters(left: dict, right: dict) -> tuple[float, dict]:
    same_domain = 1.0 if left["metadata"].get("canonical_domain") == right["metadata"].get("canonical_domain") else 0.0
    location_match = 1.0 if left["metadata"].get("top_location") and left["metadata"].get("top_location") == right["metadata"].get("top_location") else 0.0
    left_subs = set(left["metadata"].get("top_subdomains", []))
    right_subs = set(right["metadata"].get("top_subdomains", []))
    subdomain_overlap = len(left_subs & right_subs) / max(len(left_subs | right_subs), 1)
    weak_size = 1.0 if max(left["save_count"], right["save_count"]) <= 2 else 0.4 if max(left["save_count"], right["save_count"]) <= 3 else 0.0
    entropy_pressure = min((left["entropy"] + right["entropy"]) / 2.0, 1.0)
    embedding_pressure = cosine_similarity(left.get("embedding_vector", []), right.get("embedding_vector", []))
    score = (
        same_domain * 0.20 +
        location_match * 0.20 +
        subdomain_overlap * 0.20 +
        weak_size * 0.20 +
        entropy_pressure * 0.10 +
        embedding_pressure * 0.10
    )
    return score, {
        "same_domain": same_domain,
        "location_match": location_match,
        "subdomain_overlap": subdomain_overlap,
        "weak_size": weak_size,
        "entropy_pressure": entropy_pressure,
        "embedding_similarity": embedding_pressure,
    }
