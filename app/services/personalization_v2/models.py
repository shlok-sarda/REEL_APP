from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReelItemRecord:
    reel_item_id: int
    reel_id: str
    user_id: str
    received_at: str
    primary_category: str
    specific_category: str
    item_name: str
    summary: str
    url: str
    product_name: str = ""
    brand: str = ""
    model: str = ""
    product_type: str = ""
    search_query: str = ""


@dataclass
class StructuredFeature:
    reel_item_id: int
    reel_id: str
    user_id: str
    primary_category: str
    specific_category: str
    item_name: str
    summary: str
    item_type: str
    canonical_domain: str
    subdomains: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    location: str = ""
    vibe: list[str] = field(default_factory=list)
    intent: str = ""
    audience_context: str = ""
    confidence_scores: dict[str, float] = field(default_factory=dict)
    embedding_id: int | None = None
    embedding_vector: list[float] = field(default_factory=list)
    interpretation_status: str = "ready"
    interpretation_source: str = "llm+normalization"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClusterCandidate:
    node_id: str
    canonical_key: str
    display_hint: str
    confidence: float
    save_count: int
    recent_save_count: int
    growth_velocity: float
    entropy: float
    embedding_vector: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssignmentDecision:
    cluster_node_id: str
    cluster_key: str
    assignment_score: float
    confidence: float
    action: str
    reasons: dict[str, Any] = field(default_factory=dict)

