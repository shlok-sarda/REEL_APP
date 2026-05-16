from __future__ import annotations

import hashlib
import math

from api_config import get_openai_client


EMBEDDING_MODEL = "text-embedding-3-small"
FALLBACK_DIM = 96


def l2_normalize(vector: list[float]) -> list[float]:
    if not vector:
        return []
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return [0.0 for _ in vector]
    return [value / magnitude for value in vector]


def deterministic_embedding(text: str, dimensions: int = FALLBACK_DIM) -> list[float]:
    buckets = [0.0] * dimensions
    source = (text or "").encode("utf-8")
    digest = hashlib.sha256(source).digest() or b"\x00"
    for index, byte in enumerate(digest * ((dimensions // len(digest)) + 1)):
        if index >= dimensions:
            break
        buckets[index] = (byte / 255.0) - 0.5
    return l2_normalize(buckets)


def embed_text(text: str, use_remote: bool = True) -> tuple[list[float], str]:
    normalized = (text or "").strip()
    if not normalized:
        return deterministic_embedding("empty"), "deterministic-empty"

    if use_remote:
        try:
            client = get_openai_client()
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=[normalized],
            )
            vector = response.data[0].embedding
            return l2_normalize(vector), EMBEDDING_MODEL
        except Exception:
            return deterministic_embedding(normalized), "deterministic-fallback"
    else:
        return deterministic_embedding(normalized), "deterministic-fallback"


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))
