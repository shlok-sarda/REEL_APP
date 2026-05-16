from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from app.db.database import get_connection
from app.services.personalization_v2.models import ClusterCandidate, ReelItemRecord, StructuredFeature


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def dumps_json(value) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def loads_json(value: str, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def slugify(value: str) -> str:
    chars = []
    last_dash = False
    for char in (value or "").lower():
        if char.isalnum():
            chars.append(char)
            last_dash = False
        elif not last_dash:
            chars.append("-")
            last_dash = True
    return "".join(chars).strip("-") or "node"


class PersonalizationV2Repository:
    def reset_user_state(self, user_id: str) -> None:
        with get_connection() as connection:
            embedding_ids = [
                row["embedding_id"]
                for row in connection.execute(
                    "SELECT embedding_id FROM reel_item_features WHERE user_id = ? AND embedding_id IS NOT NULL",
                    (user_id,),
                ).fetchall()
            ]
            cluster_embedding_ids = [
                row["centroid_embedding_id"]
                for row in connection.execute(
                    "SELECT centroid_embedding_id FROM user_interest_nodes WHERE user_id = ? AND centroid_embedding_id IS NOT NULL",
                    (user_id,),
                ).fetchall()
            ]
            embedding_ids = [value for value in embedding_ids + cluster_embedding_ids if value]

            cluster_node_ids = [
                row["id"]
                for row in connection.execute(
                    "SELECT id FROM user_interest_nodes WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
            ]
            if cluster_node_ids:
                placeholders = ",".join("?" for _ in cluster_node_ids)
                connection.execute(f"DELETE FROM cluster_titles WHERE cluster_node_id IN ({placeholders})", cluster_node_ids)
                connection.execute(f"DELETE FROM cluster_memberships WHERE cluster_node_id IN ({placeholders})", cluster_node_ids)
                connection.execute(f"DELETE FROM cluster_events WHERE cluster_node_id IN ({placeholders})", cluster_node_ids)
                connection.execute(
                    f"DELETE FROM user_interest_edges WHERE from_node_id IN ({placeholders}) OR to_node_id IN ({placeholders})",
                    cluster_node_ids + cluster_node_ids,
                )
            connection.execute("DELETE FROM user_interest_nodes WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM cluster_memberships WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM reel_item_features WHERE user_id = ?", (user_id,))

            if embedding_ids:
                placeholders = ",".join("?" for _ in embedding_ids)
                connection.execute(f"DELETE FROM embedding_store WHERE id IN ({placeholders})", embedding_ids)

    def load_reel_items(self, user_id: str) -> list[ReelItemRecord]:
        query = """
            SELECT
                ri.id AS reel_item_id,
                ri.reel_id AS reel_id,
                r.user_id AS user_id,
                r.received_at AS received_at,
                ri.primary_category AS primary_category,
                ri.secondary_category AS specific_category,
                ri.item_name AS item_name,
                ri.summary AS summary,
                r.url AS url,
                COALESCE(pl.product_name, '') AS product_name,
                COALESCE(pl.brand, '') AS brand,
                COALESCE(pl.model, '') AS model,
                COALESCE(pl.product_type, '') AS product_type,
                COALESCE(pl.search_query, '') AS search_query
            FROM reel_items ri
            JOIN reels r ON r.id = ri.reel_id
            LEFT JOIN product_links pl ON pl.reel_item_id = ri.id
            WHERE r.user_id = ?
            ORDER BY r.received_at ASC, ri.id ASC
        """
        with get_connection() as connection:
            rows = connection.execute(query, (user_id,)).fetchall()
        return [ReelItemRecord(**dict(row)) for row in rows]

    def upsert_embedding(self, object_type: str, object_id: str, model: str, version: str, vector: list[float], source_text_hash: str) -> int:
        created_at = now_iso()
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM embedding_store
                WHERE object_type = ? AND object_id = ? AND model = ? AND version = ?
                LIMIT 1
                """,
                (object_type, object_id, model, version),
            ).fetchone()
            if row:
                connection.execute(
                    """
                    UPDATE embedding_store
                    SET vector_json = ?, source_text_hash = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (dumps_json(vector), source_text_hash, created_at, row["id"]),
                )
                return int(row["id"])
            cursor = connection.execute(
                """
                INSERT INTO embedding_store (
                    object_type, object_id, model, version, vector_json, source_text_hash, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (object_type, object_id, model, version, dumps_json(vector), source_text_hash, created_at, created_at),
            )
            return int(cursor.lastrowid)

    def upsert_feature(self, feature: StructuredFeature) -> None:
        created_at = now_iso()
        with get_connection() as connection:
            row = connection.execute(
                "SELECT id FROM reel_item_features WHERE reel_item_id = ? LIMIT 1",
                (feature.reel_item_id,),
            ).fetchone()
            payload = (
                feature.user_id,
                feature.reel_id,
                feature.reel_item_id,
                feature.primary_category,
                feature.specific_category,
                feature.item_name,
                feature.summary,
                feature.item_type,
                feature.canonical_domain,
                dumps_json(feature.subdomains),
                dumps_json(feature.entities),
                feature.location,
                dumps_json(feature.vibe),
                feature.intent,
                feature.audience_context,
                dumps_json(feature.confidence_scores),
                feature.embedding_id,
                feature.interpretation_status,
                feature.interpretation_source,
                dumps_json(feature.metadata),
            )
            if row:
                connection.execute(
                    """
                    UPDATE reel_item_features
                    SET user_id = ?, reel_id = ?, primary_category = ?, specific_category = ?, item_name = ?, summary = ?,
                        item_type = ?, canonical_domain = ?, canonical_subdomains_json = ?, canonical_entities_json = ?,
                        canonical_location = ?, vibe_json = ?, intent = ?, audience_context = ?, confidence_scores_json = ?,
                        embedding_id = ?, interpretation_status = ?, interpretation_source = ?, metadata_json = ?, updated_at = ?
                    WHERE reel_item_id = ?
                    """,
                    (
                        feature.user_id,
                        feature.reel_id,
                        feature.primary_category,
                        feature.specific_category,
                        feature.item_name,
                        feature.summary,
                        feature.item_type,
                        feature.canonical_domain,
                        dumps_json(feature.subdomains),
                        dumps_json(feature.entities),
                        feature.location,
                        dumps_json(feature.vibe),
                        feature.intent,
                        feature.audience_context,
                        dumps_json(feature.confidence_scores),
                        feature.embedding_id,
                        feature.interpretation_status,
                        feature.interpretation_source,
                        dumps_json(feature.metadata),
                        created_at,
                        feature.reel_item_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO reel_item_features (
                        user_id, reel_id, reel_item_id, primary_category, specific_category, item_name, summary,
                        item_type, canonical_domain, canonical_subdomains_json, canonical_entities_json,
                        canonical_location, vibe_json, intent, audience_context, confidence_scores_json,
                        embedding_id, interpretation_status, interpretation_source, metadata_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload + (created_at, created_at),
                )

    def load_features(self, user_id: str) -> list[StructuredFeature]:
        query = """
            SELECT *
            FROM reel_item_features
            WHERE user_id = ?
            ORDER BY id ASC
        """
        with get_connection() as connection:
            rows = connection.execute(query, (user_id,)).fetchall()
            embeddings = {
                row["id"]: loads_json(row["vector_json"], [])
                for row in connection.execute("SELECT id, vector_json FROM embedding_store").fetchall()
            }

        features = []
        for row in rows:
            features.append(
                StructuredFeature(
                    reel_item_id=row["reel_item_id"],
                    reel_id=row["reel_id"],
                    user_id=row["user_id"],
                    primary_category=row["primary_category"],
                    specific_category=row["specific_category"],
                    item_name=row["item_name"],
                    summary=row["summary"],
                    item_type=row["item_type"],
                    canonical_domain=row["canonical_domain"],
                    subdomains=loads_json(row["canonical_subdomains_json"], []),
                    entities=loads_json(row["canonical_entities_json"], []),
                    location=row["canonical_location"],
                    vibe=loads_json(row["vibe_json"], []),
                    intent=row["intent"],
                    audience_context=row["audience_context"],
                    confidence_scores=loads_json(row["confidence_scores_json"], {}),
                    embedding_id=row["embedding_id"],
                    embedding_vector=embeddings.get(row["embedding_id"], []) if row["embedding_id"] else [],
                    interpretation_status=row["interpretation_status"],
                    interpretation_source=row["interpretation_source"],
                    metadata=loads_json(row["metadata_json"], {}),
                )
            )
        return features

    def reset_user_graph(self, user_id: str) -> None:
        with get_connection() as connection:
            cluster_node_ids = [
                row["id"]
                for row in connection.execute(
                    "SELECT id FROM user_interest_nodes WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
            ]
            if cluster_node_ids:
                placeholders = ",".join("?" for _ in cluster_node_ids)
                connection.execute(f"DELETE FROM cluster_titles WHERE cluster_node_id IN ({placeholders})", cluster_node_ids)
                connection.execute(f"DELETE FROM cluster_memberships WHERE cluster_node_id IN ({placeholders})", cluster_node_ids)
                connection.execute(f"DELETE FROM cluster_events WHERE cluster_node_id IN ({placeholders})", cluster_node_ids)
                connection.execute(
                    f"DELETE FROM user_interest_edges WHERE from_node_id IN ({placeholders}) OR to_node_id IN ({placeholders})",
                    cluster_node_ids + cluster_node_ids,
                )
            connection.execute("DELETE FROM user_interest_nodes WHERE user_id = ?", (user_id,))

    def upsert_node(
        self,
        user_id: str,
        node_type: str,
        canonical_key: str,
        display_hint: str,
        parent_node_id: str = "",
        state: str = "active",
        metadata: dict | None = None,
        confidence: float = 0.0,
        centroid_embedding_id: int | None = None,
    ) -> str:
        created_at = now_iso()
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM user_interest_nodes
                WHERE user_id = ? AND node_type = ? AND canonical_key = ?
                LIMIT 1
                """,
                (user_id, node_type, canonical_key),
            ).fetchone()
            if row:
                connection.execute(
                    """
                    UPDATE user_interest_nodes
                    SET display_hint = ?, parent_node_id = ?, state = ?, metadata_json = ?, confidence = ?, centroid_embedding_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (display_hint, parent_node_id, state, dumps_json(metadata or {}), confidence, centroid_embedding_id, created_at, row["id"]),
                )
                return row["id"]

            node_id = f"{node_type}_{slugify(canonical_key)}_{uuid.uuid4().hex[:8]}"
            connection.execute(
                """
                INSERT INTO user_interest_nodes (
                    id, user_id, node_type, canonical_key, display_hint, parent_node_id,
                    state, save_count, recent_save_count, growth_velocity, entropy, confidence,
                    centroid_embedding_id, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?, ?, ?, ?, ?)
                """,
                (node_id, user_id, node_type, canonical_key, display_hint, parent_node_id, state, confidence, centroid_embedding_id, dumps_json(metadata or {}), created_at, created_at),
            )
            return node_id

    def replace_cluster_memberships(self, user_id: str, assignments: list[dict]) -> None:
        created_at = now_iso()
        with get_connection() as connection:
            connection.execute("DELETE FROM cluster_memberships WHERE user_id = ?", (user_id,))
            for assignment in assignments:
                connection.execute(
                    """
                    INSERT INTO cluster_memberships (
                        user_id, reel_item_id, cluster_node_id, assignment_score,
                        assignment_reason_json, assignment_version, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        assignment["reel_item_id"],
                        assignment["cluster_node_id"],
                        assignment["assignment_score"],
                        dumps_json(assignment["assignment_reason"]),
                        assignment.get("assignment_version", "v2-initial"),
                        created_at,
                        created_at,
                    ),
                )

    def replace_edges(self, user_id: str, edges: list[dict]) -> None:
        created_at = now_iso()
        with get_connection() as connection:
            connection.execute("DELETE FROM user_interest_edges WHERE user_id = ?", (user_id,))
            for edge in edges:
                edge_id = f"edge_{uuid.uuid4().hex[:10]}"
                connection.execute(
                    """
                    INSERT INTO user_interest_edges (
                        id, user_id, from_node_id, to_node_id, edge_type, weight,
                        evidence_count, metadata_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        edge_id,
                        user_id,
                        edge["from_node_id"],
                        edge["to_node_id"],
                        edge["edge_type"],
                        edge["weight"],
                        edge.get("evidence_count", 1),
                        dumps_json(edge.get("metadata", {})),
                        created_at,
                        created_at,
                    ),
                )

    def update_node_metrics(self, node_id: str, metrics: dict) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE user_interest_nodes
                SET save_count = ?, recent_save_count = ?, growth_velocity = ?, entropy = ?,
                    confidence = ?, centroid_embedding_id = ?, metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    metrics.get("save_count", 0),
                    metrics.get("recent_save_count", 0),
                    metrics.get("growth_velocity", 0.0),
                    metrics.get("entropy", 0.0),
                    metrics.get("confidence", 0.0),
                    metrics.get("centroid_embedding_id"),
                    dumps_json(metrics.get("metadata", {})),
                    now_iso(),
                    node_id,
                ),
            )

    def replace_cluster_titles(self, cluster_titles: list[dict]) -> None:
        created_at = now_iso()
        with get_connection() as connection:
            for row in cluster_titles:
                connection.execute("UPDATE cluster_titles SET is_active = 0 WHERE cluster_node_id = ?", (row["cluster_node_id"],))
                connection.execute(
                    """
                    INSERT INTO cluster_titles (
                        cluster_node_id, title, title_confidence, generation_reason_json, is_active, created_at
                    )
                    VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (row["cluster_node_id"], row["title"], row["title_confidence"], dumps_json(row.get("generation_reason", {})), created_at),
                )

    def create_cluster_event(self, user_id: str, cluster_node_id: str, event_type: str, reason: dict, source_ids: list[str] | None = None, target_ids: list[str] | None = None) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO cluster_events (
                    user_id, cluster_node_id, event_type, source_cluster_ids_json,
                    target_cluster_ids_json, reason_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    cluster_node_id,
                    event_type,
                    dumps_json(source_ids or []),
                    dumps_json(target_ids or []),
                    dumps_json(reason),
                    now_iso(),
                ),
            )

    def load_cluster_candidates(self, user_id: str) -> list[ClusterCandidate]:
        with get_connection() as connection:
            node_rows = connection.execute(
                "SELECT * FROM user_interest_nodes WHERE user_id = ? AND node_type = 'cluster' ORDER BY save_count DESC, updated_at DESC",
                (user_id,),
            ).fetchall()
            embeddings = {
                row["id"]: loads_json(row["vector_json"], [])
                for row in connection.execute("SELECT id, vector_json FROM embedding_store").fetchall()
            }
        return [
            ClusterCandidate(
                node_id=row["id"],
                canonical_key=row["canonical_key"],
                display_hint=row["display_hint"],
                confidence=row["confidence"],
                save_count=row["save_count"],
                recent_save_count=row["recent_save_count"],
                growth_velocity=row["growth_velocity"],
                entropy=row["entropy"],
                embedding_vector=embeddings.get(row["centroid_embedding_id"], []) if row["centroid_embedding_id"] else [],
                metadata=loads_json(row["metadata_json"], {}),
            )
            for row in node_rows
        ]

    def load_debug_snapshot(self, user_id: str) -> dict:
        with get_connection() as connection:
            nodes = [dict(row) for row in connection.execute("SELECT * FROM user_interest_nodes WHERE user_id = ? ORDER BY node_type, save_count DESC, canonical_key ASC", (user_id,)).fetchall()]
            edges = [dict(row) for row in connection.execute("SELECT * FROM user_interest_edges WHERE user_id = ? ORDER BY edge_type, weight DESC", (user_id,)).fetchall()]
            memberships = [dict(row) for row in connection.execute("SELECT * FROM cluster_memberships WHERE user_id = ? ORDER BY assignment_score DESC", (user_id,)).fetchall()]
            titles = [dict(row) for row in connection.execute("SELECT * FROM cluster_titles WHERE cluster_node_id IN (SELECT id FROM user_interest_nodes WHERE user_id = ?) AND is_active = 1", (user_id,)).fetchall()]
            features = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT
                        rif.*,
                        COALESCE(r.url, '') AS url
                    FROM reel_item_features rif
                    LEFT JOIN reels r ON r.id = rif.reel_id
                    WHERE rif.user_id = ?
                    ORDER BY rif.reel_item_id ASC
                    """,
                    (user_id,),
                ).fetchall()
            ]

        for collection in (nodes, edges, memberships, titles, features):
            for row in collection:
                for key, value in list(row.items()):
                    if key.endswith("_json"):
                        row[key] = loads_json(value, {})

        return {
            "user_id": user_id,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "membership_count": len(memberships),
            "title_count": len(titles),
            "feature_count": len(features),
            "nodes": nodes,
            "edges": edges,
            "memberships": memberships,
            "titles": titles,
            "features": features,
        }
