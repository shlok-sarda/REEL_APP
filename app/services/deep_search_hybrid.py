"""Hybrid deep search — production port of the proven Deep Search Lab engine.

Layers (all validated in deep_search_lab, 21/21 eval on OpenAI + local):
  lexical   : in-memory SQLite FTS5, per-query, over the user's persisted
              deep_search_documents. Passes: phrase / all-words / any-words /
              focus (identity fields only).
  semantic  : OpenAI text-embedding-3-small, brute-force cosine over vectors
              persisted in embedding_store. Dual vector per reel (subject +
              context), subject-weighted blend.
  fusion    : weighted Reciprocal Rank Fusion across the passes.
  gate      : multi-path admission (see search_documents_hybrid), calibrated
              2026-07-11 against real prod data. A pure z-score gate fails in
              BOTH directions — measured: on a small homogeneous library
              ("girls" over a mostly-girls library) every true match clusters
              together so nothing reaches z>=2.35 and search returns ZERO;
              on a diverse library, nonsense queries ("blorptastic frimble")
              produce lone statistical outliers that z ADMITS (sim 0.350 —
              higher than a true "makeup" match at 0.337, proving absolute
              cosine can't separate either). The separator that DOES hold in
              every measured case: true matches carry the query term (or a
              synonym) in vision-grounded fields — text the vision model
              observed — while junk never does. Captions/hashtags/transcript
              stay untrusted (keyword-stuffing).

Design constraints for production safety:
  * Reuses embed_text / upsert_embedding / _result_payload — no new infra.
  * Query embedding is ONE OpenAI call per search; doc embeddings are built at
    index time and cached by content hash (no re-charge on unchanged reels).
  * If OpenAI is unavailable the caller falls back to lexical-only search;
    this module never raises for a missing/failed embedding.

`main_subject` (the v2 extraction field: "what is this video actually about,
visually") is wired at top weight in _SUBJECT_FIELDS, FTS_COLUMNS and
FOCUS_COLUMNS. Reels processed before it shipped simply have it empty and are
carried by the vision-grounded wide pass over visual_summary/visual_entities.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections import defaultdict
from typing import Any

import numpy as np

from app.db.database import get_connection
from app.services.personalization_v2.embeddings import EMBEDDING_MODEL, l2_normalize

EMBED_OBJECT_TYPE = "deep_search_reel"
EMBED_VERSION = "hybrid_v1"

RRF_K = 60
ENGINE_WEIGHTS = {"semantic": 1.0, "phrase": 1.0, "and": 0.7, "or": 0.4, "focus": 0.9, "wide": 0.85}
SUBJECT_BLEND = 0.6

# Gate thresholds — OpenAI text-embedding-3-small cosine scale. All values are
# MEASURED (2026-07-11 calibration on the real 9-reel prod library replica +
# the 51-reel lab set through this exact code), not guessed:
#   SEM_ABS_MIN   loose noise floor. Nonsense tops out ~0.17 on small sets;
#                 true matches can sit as low as 0.16 (admitted via the wide
#                 pass instead, never semantic-only).
#   SEM_Z_MIN     standout path for diverse libraries (unchanged from lab).
#   SEM_TOP_FLOOR relative path arms only when the best hit is genuinely
#                 strong. 0.30 sits between the strongest measured off-topic
#                 top (travel@9 second-place 0.274 / cricket@51 top 0.272) and
#                 the weakest measured on-topic top ("makeup"@9 = 0.337).
#   SEM_REL       within-query band. Needs <=0.834 (makeup's #2 true match at
#                 0.281/0.337) and >0.674 (makeup's first FALSE match at
#                 0.227/0.337). 0.80 has margin on both sides.
SEM_ABS_MIN = 0.20
SEM_Z_MIN = 2.35
SEM_TOP_FLOOR = 0.30
SEM_REL = 0.80

# FTS columns → production document fields, with BM25 weights. main_subject
# ("what is this video actually about, visually" — v2 extraction) outranks
# everything; empty on reels processed before it shipped, which is harmless.
# Names/products/entities rank next; transcript/caption lowest.
FTS_COLUMNS: list[tuple[str, float]] = [
    ("main_subject", 14.0),
    ("item_names", 12.0),
    ("product_names", 11.0),
    ("brands", 11.0),
    ("models", 10.0),
    ("collection_titles", 10.0),
    ("entities", 10.0),
    ("locations", 9.0),
    ("parent_titles", 8.0),
    ("subdomains", 8.0),
    ("categories", 7.0),
    ("item_summaries", 6.0),
    ("visual_summary", 3.5),
    ("visible_text", 3.0),
    ("visual_entities", 3.0),
    ("caption", 3.0),
    ("transcript", 2.0),
    ("hashtags", 1.5),
]

# Single-word queries: a hit in an identity field is strong evidence; a hit in
# caption/transcript is only a recall net.
FOCUS_COLUMNS = [
    "main_subject", "item_names", "product_names", "brands", "models",
    "collection_titles", "entities", "categories", "parent_titles",
]

# Vision-grounded / trusted fields for the "wide" admission pass: identity
# fields plus text the VISION MODEL produced about the reel (visual_summary
# saying "a young woman films a selfie" is observed evidence that survives a
# "girls" query even when no identity field mentions a person). Deliberately
# excludes caption/hashtags/transcript — creator-typed text, the
# keyword-stuffing vector the old gate existed to block.
WIDE_COLUMNS = FOCUS_COLUMNS + [
    "locations", "subdomains", "item_summaries",
    "visual_summary", "visual_entities", "visible_text",
]

# Fields that describe what the reel IS (tight subject vector).
_SUBJECT_FIELDS = [
    "main_subject", "item_names", "categories", "entities", "product_names", "brands", "product_types",
]

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "that",
    "the", "to", "was", "what", "when", "where", "which", "with", "you",
}

IRREGULAR_PLURALS = {
    "women": "woman", "men": "man", "children": "child", "people": "person",
    "feet": "foot", "teeth": "tooth", "mice": "mouse", "geese": "goose",
    "mens": "man", "womens": "woman", "childrens": "child", "peoples": "person",
}

SYNONYMS = {
    "girl": ["woman"], "woman": ["girl", "lady"], "lady": ["woman", "girl"],
    "ladies": ["woman", "girl"], "guy": ["man", "dude"], "man": ["guy"],
    "dude": ["man", "guy"], "shoe": ["sneaker", "footwear"],
    "sneaker": ["shoe", "footwear"],
}


def canonicalize(text: str) -> str:
    if not text:
        return ""
    return re.sub(
        r"[A-Za-z]+",
        lambda m: IRREGULAR_PLURALS.get(m.group(0).lower(), m.group(0)),
        text,
    )


def _join(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return ", ".join(_join(v) for v in value if v)
    if isinstance(value, dict):
        return ", ".join(_join(v) for v in value.values() if v)
    return str(value)


def _fts_fields(document: dict) -> dict[str, str]:
    """Production document → the text that backs each FTS column."""
    categories = _join([document.get("primary_category"), document.get("secondary_category")])
    subdomains = _join(document.get("subdomains"))
    return {
        "main_subject": _join(document.get("main_subject")),
        "item_names": _join(document.get("item_names")),
        "product_names": _join(document.get("product_names")),
        "brands": _join(document.get("brands")),
        "models": _join(document.get("models")),
        "collection_titles": _join(document.get("collection_titles")),
        "entities": _join(document.get("entities")),
        "locations": _join(document.get("locations")),
        "parent_titles": _join(document.get("parent_titles")),
        "subdomains": subdomains,
        "categories": categories,
        "item_summaries": _join(document.get("item_summaries")),
        "visual_summary": _join(document.get("visual_summary")),
        "visible_text": _join(document.get("visible_text")),
        "visual_entities": _join(document.get("visual_entities")),
        "caption": _join(document.get("caption")),
        "transcript": _join(document.get("transcript")),
        "hashtags": _join(document.get("hashtags")),
    }


def subject_text(document: dict) -> str:
    fields = _fts_fields(document)
    parts = [fields.get(name, "") for name in _SUBJECT_FIELDS]
    return "\n".join(p for p in parts if p.strip())


def context_text(document: dict) -> str:
    fields = _fts_fields(document)
    parts = [
        subject_text(document),
        fields.get("subdomains", ""),
        fields.get("locations", ""),
        _join(document.get("vibes")),
        _join(document.get("intents")),
        fields.get("visual_summary", ""),
        fields.get("visual_entities", ""),
        fields.get("collection_titles", ""),
        fields.get("parent_titles", ""),
        fields.get("caption", "")[:600],
    ]
    return "\n".join(p for p in parts if p and p.strip())


def content_hash(document: dict) -> str:
    return hashlib.sha256(
        f"{EMBEDDING_MODEL}:{subject_text(document)}::{context_text(document)}".encode()
    ).hexdigest()


# --------------------------------------------------------------------------
# embedding (remote-only; deterministic fallback would break cosine vs OpenAI)
# --------------------------------------------------------------------------

EMBED_BATCH_SIZE = 128


def embed_remote(text: str) -> list[float] | None:
    """OpenAI embedding for a single text (used for the query at search time).
    Returns None on any failure so callers degrade to lexical-only rather than
    mixing incompatible vectors."""
    result = embed_remote_batch([text])
    return result[0] if result else None


def embed_remote_batch(texts: list[str]) -> list[list[float] | None] | None:
    """Batch OpenAI embedding, L2-normalized, preserving order. Empty strings
    map to None. Returns None entirely if the API call fails (caller degrades).
    Batching is essential at scale: one call embeds up to EMBED_BATCH_SIZE
    reels, so a 500-reel backfill is ~10 calls, not 1000."""
    cleaned = [(t or "").strip() for t in texts]
    non_empty = [(i, t) for i, t in enumerate(cleaned) if t]
    if not non_empty:
        return [None] * len(texts)
    out: list[list[float] | None] = [None] * len(texts)
    try:
        from api_config import get_openai_client

        client = get_openai_client()
        for start in range(0, len(non_empty), EMBED_BATCH_SIZE):
            chunk = non_empty[start:start + EMBED_BATCH_SIZE]
            response = client.embeddings.create(
                model=EMBEDDING_MODEL, input=[t for _, t in chunk]
            )
            for (idx, _), item in zip(chunk, response.data):
                out[idx] = l2_normalize(item.embedding)
    except Exception:
        return None
    return out


def index_document_embeddings(documents: list[dict]) -> dict[str, Any]:
    """Build + persist subject/context vectors for docs whose content changed.
    Batched so a full backfill of hundreds of reels is a handful of API calls.
    Non-fatal: returns a report; never raises. Skips silently if OpenAI down."""
    todo = []  # (reel_id, digest, subject_text, context_text)
    skipped = 0
    for document in documents:
        reel_id = document.get("reel_id")
        if not reel_id:
            continue
        digest = content_hash(document)
        if _load_vector(reel_id, "subject") is not None and _stored_hash(reel_id) == digest:
            skipped += 1
            continue
        todo.append((reel_id, digest, subject_text(document) or context_text(document), context_text(document)))

    if not todo:
        return {"embedded": 0, "skipped": skipped, "failed": 0, "total": len(documents)}

    subj_vecs = embed_remote_batch([t[2] for t in todo])
    ctx_vecs = embed_remote_batch([t[3] for t in todo])
    if subj_vecs is None or ctx_vecs is None:
        # OpenAI unavailable — leave everything unembedded; search stays lexical.
        return {"embedded": 0, "skipped": skipped, "failed": len(todo), "total": len(documents)}

    embedded = failed = 0
    for (reel_id, digest, _, _), subj, ctx in zip(todo, subj_vecs, ctx_vecs):
        if subj is None or ctx is None:
            failed += 1
            continue
        _upsert_vector(f"{reel_id}:subject", subj, digest)
        _upsert_vector(f"{reel_id}:context", ctx, digest)
        embedded += 1
    return {"embedded": embedded, "skipped": skipped, "failed": failed, "total": len(documents)}


def _upsert_vector(object_id: str, vector: list[float], source_hash: str) -> None:
    import json
    from datetime import datetime

    now = datetime.now().isoformat(timespec="seconds")
    payload = json.dumps(vector)
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id FROM embedding_store WHERE object_type = ? AND object_id = ? AND model = ? AND version = ? LIMIT 1",
            (EMBED_OBJECT_TYPE, object_id, EMBEDDING_MODEL, EMBED_VERSION),
        ).fetchone()
        if row:
            connection.execute(
                "UPDATE embedding_store SET vector_json = ?, source_text_hash = ?, updated_at = ? WHERE id = ?",
                (payload, source_hash, now, row["id"]),
            )
        else:
            connection.execute(
                "INSERT INTO embedding_store (object_type, object_id, model, version, vector_json, source_text_hash, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (EMBED_OBJECT_TYPE, object_id, EMBEDDING_MODEL, EMBED_VERSION, payload, source_hash, now, now),
            )


def _stored_hash(reel_id: str) -> str:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT source_text_hash FROM embedding_store WHERE object_type = ? AND object_id = ? AND version = ? LIMIT 1",
            (EMBED_OBJECT_TYPE, f"{reel_id}:subject", EMBED_VERSION),
        ).fetchone()
    return row["source_text_hash"] if row else ""


def _load_vector(reel_id: str, kind: str) -> list[float] | None:
    import json

    with get_connection() as connection:
        row = connection.execute(
            "SELECT vector_json FROM embedding_store WHERE object_type = ? AND object_id = ? AND version = ? LIMIT 1",
            (EMBED_OBJECT_TYPE, f"{reel_id}:{kind}", EMBED_VERSION),
        ).fetchone()
    if not row:
        return None
    try:
        vec = json.loads(row["vector_json"])
        return vec if isinstance(vec, list) and vec else None
    except Exception:
        return None


# --------------------------------------------------------------------------
# search
# --------------------------------------------------------------------------

def _tokens(query: str) -> list[str]:
    return [canonicalize(t) for t in re.findall(r"[a-z0-9]+", query.casefold())]


def _synonyms_for(token: str) -> list[str]:
    """Synonym lookup that survives regular plurals. Measured bug this fixes:
    'girls' never matched SYNONYMS['girl'], so the girl→woman expansion only
    fired for the singular — the plural query lost all its true matches.
    (Irregular plurals are already canonicalized by _tokens; FTS porter
    stemming handles plural/singular *within* the index, but the synonym dict
    lookup happens before FTS and needs its own fallback.)"""
    if token in SYNONYMS:
        return SYNONYMS[token]
    for suffix in ("es", "s"):
        stem = token[: -len(suffix)]
        if token.endswith(suffix) and stem in SYNONYMS:
            return SYNONYMS[stem]
    return []


def _variants(token: str) -> list[str]:
    return list(dict.fromkeys([token] + _synonyms_for(token)))


def _quote(term: str) -> str:
    # Quoted FTS5 phrase: neutralizes operator characters, tokenizer still runs.
    return '"' + term.replace('"', "") + '"'


class _Index:
    """In-memory FTS + vector matrices built from one user's documents."""

    def __init__(self, documents: list[dict], load_vectors: bool = True):
        self.documents = documents
        self.by_id = {d["reel_id"]: d for d in documents if d.get("reel_id")}
        self._build_fts()
        if load_vectors:
            self._load_vectors()
        else:
            # lexical-only mode (degraded search when OpenAI is unavailable)
            self.vector_ids = []
            self.subject_matrix = None
            self.context_matrix = None

    def _build_fts(self):
        self.db = sqlite3.connect(":memory:")
        cols = ", ".join(name for name, _ in FTS_COLUMNS)
        self.db.execute(
            f"CREATE VIRTUAL TABLE fts USING fts5(reel_id UNINDEXED, {cols}, tokenize='porter unicode61')"
        )
        names = ["reel_id"] + [n for n, _ in FTS_COLUMNS]
        placeholders = ", ".join("?" for _ in names)
        for document in self.documents:
            rid = document.get("reel_id")
            if not rid:
                continue
            fields = _fts_fields(document)
            values = [rid] + [canonicalize(fields[n]) for n, _ in FTS_COLUMNS]
            self.db.execute(f"INSERT INTO fts ({', '.join(names)}) VALUES ({placeholders})", values)

    def _load_vectors(self):
        self.vector_ids, subj, ctx = [], [], []
        for rid in self.by_id:
            sv = _load_vector(rid, "subject")
            cv = _load_vector(rid, "context")
            if sv and cv:
                self.vector_ids.append(rid)
                subj.append(sv)
                ctx.append(cv)
        self.subject_matrix = np.asarray(subj, dtype=np.float32) if subj else None
        self.context_matrix = np.asarray(ctx, dtype=np.float32) if ctx else None

    def _fts(self, expr: str) -> list[str]:
        weights = ", ".join(str(w) for _, w in FTS_COLUMNS)
        try:
            rows = self.db.execute(
                f"SELECT reel_id, bm25(fts, 0, {weights}) AS s FROM fts WHERE fts MATCH ? ORDER BY s LIMIT 60",
                (expr,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [r[0] for r in rows]

    def lexical_ranks(self, query: str) -> dict[str, list[str]]:
        """Ranked lists per lexical pass. Beyond the original four:
          wide     : every meaningful term (or a synonym) present in the
                     TRUSTED fields (WIDE_COLUMNS) — vision-grounded coverage,
                     immune to caption keyword-stuffing. Admission-grade.
          wide_any : ANY meaningful term (or synonym) present in trusted
                     fields of ANY doc — the corpus-grounding probe that keeps
                     nonsense queries from surfacing semantic outliers."""
        tokens = _tokens(query)
        meaningful = [t for t in tokens if t not in STOPWORDS] or tokens
        out: dict[str, list[str]] = {
            "phrase": [], "and": [], "or": [], "focus": [], "wide": [], "wide_any": [],
        }
        if not tokens:
            return out
        variant_groups = [_variants(t) for t in meaningful]
        flat = list(dict.fromkeys(v for group in variant_groups for v in group))
        or_expr = " OR ".join(_quote(v) for v in flat)
        wide_cols = "{" + " ".join(WIDE_COLUMNS) + "}"
        out["wide_any"] = self._fts(f"{wide_cols}: ({or_expr})")
        if len(meaningful) == 1:
            cols = "{" + " ".join(FOCUS_COLUMNS) + "}"
            out["focus"] = self._fts(f"{cols}: ({or_expr})")
            out["wide"] = out["wide_any"]
            out["or"] = self._fts(or_expr)
            return out
        if len(tokens) >= 2:
            out["phrase"] = self._fts('"' + " ".join(tokens) + '"')
        out["and"] = self._fts(" AND ".join(_quote(t) for t in meaningful))
        out["wide"] = self._fts(
            " AND ".join(
                f"({wide_cols}: ({' OR '.join(_quote(v) for v in group)}))"
                for group in variant_groups
            )
        )
        out["or"] = self._fts(or_expr)
        return out

    def semantic_ranks(self, query_vec: list[float] | None) -> tuple[list[str], dict[str, float]]:
        if query_vec is None or self.subject_matrix is None:
            return [], {}
        vector = np.asarray(query_vec, dtype=np.float32)
        ctx_sims = self.context_matrix @ vector
        subj_sims = self.subject_matrix @ vector
        sims = np.maximum(SUBJECT_BLEND * subj_sims + (1 - SUBJECT_BLEND) * ctx_sims, ctx_sims * 0.96)
        order = np.argsort(-sims)
        ranked = [self.vector_ids[i] for i in order]
        similarity = {self.vector_ids[i]: float(sims[i]) for i in range(len(sims))}
        return ranked, similarity


def search_documents_hybrid(documents: list[dict], query: str, limit: int = 20) -> list[dict] | None:
    """Return ranked _result_payload dicts, or None if semantic is unavailable
    (caller then falls back to the existing lexical search)."""
    from app.services.deep_search import _result_payload

    query = (query or "").strip()
    if not query or not documents:
        return []

    query_vec = embed_remote(query)
    if query_vec is None:
        return None  # OpenAI unavailable → caller falls back to lexical search

    index = _Index(documents)
    if index.subject_matrix is None:
        # No doc embeddings yet (pre-backfill). Don't serve degraded FTS-only —
        # let the caller use the proven lexical search until embeddings exist.
        return None

    lex = index.lexical_ranks(query)
    sem_ranked, sims = index.semantic_ranks(query_vec)

    rank_of: dict[str, dict[str, int]] = defaultdict(dict)
    for engine, ranked in [
        ("phrase", lex["phrase"]), ("and", lex["and"]), ("or", lex["or"]),
        ("focus", lex["focus"]), ("wide", lex["wide"]), ("semantic", sem_ranked),
    ]:
        for rank, rid in enumerate(ranked):
            rank_of[rid][engine] = rank

    fused: dict[str, float] = defaultdict(float)
    for rid, engines in rank_of.items():
        for engine, rank in engines.items():
            fused[rid] += ENGINE_WEIGHTS[engine] / (RRF_K + rank + 1)

    strong_lexical = set(lex["phrase"]) | set(lex["and"]) | set(lex["focus"])
    wide = set(lex["wide"])
    grounded = bool(lex["wide_any"])
    if sims:
        vals = np.array(list(sims.values()), dtype=np.float32)
        mean, std = float(vals.mean()), float(vals.std()) or 1e-6
        top_sim = float(vals.max())
    else:
        mean, std, top_sim = 0.0, 1e-6, 0.0

    # Admission: a doc surfaces if ANY path accepts it (all calibrated —
    # see the threshold comments at the top of this module):
    #   P1 strong lexical    phrase / all-words / identity-field hit
    #   P2 vision-grounded   all query terms (or synonyms) in trusted fields
    #   P3 z-standout        statistical outlier, only for corpus-grounded
    #                        queries (kills nonsense that z alone admitted)
    #   P4 relative-to-top   within SEM_REL of a genuinely strong best hit —
    #                        rescues homogeneous libraries where no doc can
    #                        stand out from its lookalikes (the "girls over a
    #                        girls library returns zero" failure)
    ordered = sorted(fused, key=fused.get, reverse=True)
    results = []
    for rid in ordered:
        sim = sims.get(rid, 0.0)
        z = (sim - mean) / std
        admitted = (
            rid in strong_lexical
            or rid in wide
            or (grounded and sim >= SEM_ABS_MIN and z >= SEM_Z_MIN)
            or (
                grounded
                and top_sim >= SEM_TOP_FLOOR
                and sim >= SEM_ABS_MIN
                and sim >= SEM_REL * top_sim
            )
        )
        if not admitted:
            continue
        document = index.by_id.get(rid)
        if not document:
            continue
        matches = _matched_fields(document, query)
        score = int(round(fused[rid] * 100000))
        payload = _result_payload(document, score, matches)
        if sim >= SEM_ABS_MIN:
            payload.setdefault("semantic_similarity", round(sim, 4))
        results.append(payload)
        if len(results) >= limit:
            break
    return results


def search_documents_fts(documents: list[dict], query: str, limit: int = 20) -> list[dict]:
    """Degraded-mode lexical search for when OpenAI is unavailable: porter-
    stemmed BM25 FTS with synonym + plural handling, no embeddings required.
    Strictly stronger than the legacy literal matcher in deep_search.py —
    'girls' still finds reels whose visual summary says 'woman'. Trusted-field
    hits rank; the OR recall net only surfaces when nothing trusted matches
    (recall beats a blank screen in a degraded mode)."""
    from app.services.deep_search import _result_payload

    query = (query or "").strip()
    if not query or not documents:
        return []

    index = _Index(documents, load_vectors=False)
    lex = index.lexical_ranks(query)
    rank_of: dict[str, dict[str, int]] = defaultdict(dict)
    for engine, ranked in [
        ("phrase", lex["phrase"]), ("and", lex["and"]), ("or", lex["or"]),
        ("focus", lex["focus"]), ("wide", lex["wide"]),
    ]:
        for rank, rid in enumerate(ranked):
            rank_of[rid][engine] = rank

    fused: dict[str, float] = defaultdict(float)
    for rid, engines in rank_of.items():
        for engine, rank in engines.items():
            fused[rid] += ENGINE_WEIGHTS[engine] / (RRF_K + rank + 1)

    trusted = set(lex["phrase"]) | set(lex["and"]) | set(lex["focus"]) | set(lex["wide"])
    ordered = sorted(fused, key=fused.get, reverse=True)
    admitted = [rid for rid in ordered if rid in trusted] or ordered

    results = []
    for rid in admitted[:limit]:
        document = index.by_id.get(rid)
        if not document:
            continue
        score = int(round(fused[rid] * 100000))
        results.append(_result_payload(document, score, _matched_fields(document, query)))
    return results


def _matched_fields(document: dict, query: str) -> list[str]:
    tokens = [t for t in _tokens(query) if t not in STOPWORDS and len(t) > 1]
    fields = _fts_fields(document)
    matched = []
    for name, _ in FTS_COLUMNS:
        text = canonicalize(fields[name]).casefold()
        if any(re.search(rf"(?<![a-z0-9]){re.escape(t)}", text) for t in tokens):
            matched.append(_MATCH_FIELD_ALIAS.get(name, name))
    return matched


# Map FTS column names to the field keys _match_reasons() in deep_search.py
# recognizes, so the existing reason-rendering keeps working.
_MATCH_FIELD_ALIAS = {
    "main_subject": "main_subject",
    "categories": "primary_category",
    "item_names": "item_names",
    "product_names": "product_names",
    "brands": "brands",
    "models": "models",
    "entities": "entities",
    "locations": "locations",
    "collection_titles": "collection_titles",
    "parent_titles": "parent_titles",
    "visual_entities": "visual_entities",
    "visual_summary": "visual_summary",
    "visible_text": "visible_text",
    "caption": "caption",
    "transcript": "transcript",
    "hashtags": "hashtags",
    "subdomains": "subdomains",
    "item_summaries": "item_names",
}
