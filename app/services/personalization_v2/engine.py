from __future__ import annotations

from app.services.personalization_v2.embeddings import embed_text
from app.services.personalization_v2.graph_engine import ASSIGNMENT_VERSION, feature_embedding_text, rebuild_user_graph
from app.services.personalization_v2.hybrid_router import improve_snapshot_with_hybrid_router
from app.services.personalization_v2.interpreter import interpret_item
from app.services.personalization_v2.repository import PersonalizationV2Repository


class PersonalizationV2Engine:
    def __init__(self, repo: PersonalizationV2Repository | None = None):
        self.repo = repo or PersonalizationV2Repository()

    def backfill_user(
        self,
        user_id: str,
        use_llm: bool = True,
        use_remote_embeddings: bool = True,
        use_hybrid_router: bool = True,
    ) -> dict:
        self.repo.reset_user_state(user_id)
        reel_items = self.repo.load_reel_items(user_id)
        for reel_item in reel_items:
            feature = interpret_item(reel_item, use_llm=use_llm)
            feature.metadata["received_at_recency"] = 0.0
            vector, model = embed_text(feature_embedding_text(feature), use_remote=use_remote_embeddings)
            embedding_id = self.repo.upsert_embedding(
                object_type="reel_item_feature",
                object_id=str(feature.reel_item_id),
                model=model,
                version=ASSIGNMENT_VERSION,
                vector=vector,
                source_text_hash=feature_embedding_text(feature),
            )
            feature.embedding_vector = vector
            feature.embedding_id = embedding_id
            feature.metadata["received_at"] = reel_item.received_at
            self.repo.upsert_feature(feature)

        seed_snapshot = rebuild_user_graph(self.repo, user_id)
        if not use_hybrid_router:
            return seed_snapshot
        try:
            return improve_snapshot_with_hybrid_router(self.repo, user_id, seed_snapshot)
        except Exception as exc:
            print(f"[personalization_v2] hybrid router fallback for {user_id}: {exc}")
            return seed_snapshot
