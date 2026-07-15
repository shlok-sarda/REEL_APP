"""Smart folders — learned, user-owned folders with auto-routing of new reels.

Ported from the validated Deep Search Lab prototype (deep_search_lab/folders.py,
scorecard 2026-07-12: 97% held-out recall, 100% trap rejection on real data).

Distinct from personalization clusters: these are folders the USER creates
(search -> select -> name), with an AI-drafted description the user confirms.
The description IS the membership rule; new reels route in automatically.

Routing design (measured, not guessed):
  * profile = W_DESC*emb(description) + W_QUERY*emb(query) + W_CENTROID*centroid
    Folder NAMES are intentionally low-weight (W_QUERY); content drives it.
  * thresholds SELF-CALIBRATE from members' leave-one-out similarity
    (mean - k*sigma), because absolute cosine scale is not comparable — but the
    sigma margin is CAPPED and both bands sit on absolute floors, because a
    diverse folder otherwise thresholds near zero and suggests the whole
    library (observed 2026-07-15: a folder with no usable member vectors
    suggested all 232 reels).
  * pure similarity cannot separate "same template, different subject", so
    AUTO additionally requires a rare-term ANCHOR hit when the folder has any.
  * EVERY candidate — auto and suggest — must pass a cheap LLM yes/no before
    it touches memberships; verdicts are cached per (reel, description-hash).
    No verdict (API down) means the reel is skipped, never shown unvetted.
  * user rejections (with their optional "why I skipped" reasons) are fed to
    the adjudicator as negative examples, so each Skip tightens the folder.

Reel embeddings are computed from the deep-search document text and cached in
embedding_store (object_type='folder_reel'); we never use deterministic-fallback
vectors for routing (they carry no meaning) — and that now includes the
description/query vectors, which previously fell back silently and poisoned
the whole profile whenever the OpenAI key was down.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time

from app.db.database import get_connection
from app.services.library import _media_url_from_path
from app.services.personalization_v2.embeddings import (
    EMBEDDING_MODEL,
    cosine_similarity,
    embed_text,
    l2_normalize,
)

W_DESC, W_QUERY, W_CENTROID = 0.45, 0.05, 0.50
AUTO_MARGIN_SIGMA, AUTO_MARGIN_FLOOR = 1.0, 0.05
SUGGEST_MARGIN_SIGMA, SUGGEST_MARGIN_FLOOR = 2.0, 0.10
# Cap how far member diversity (sigma) can widen the suggest band, and put
# absolute floors under both bands: with text-embedding-3-small, unrelated
# reels sit ~0.15-0.25 vs a folder profile, related ones ~0.35+ (measured on
# real data 2026-07-15). Without the floors a noisy folder suggests everything.
SUGGEST_MARGIN_CAP = 0.15
ABS_AUTO_FLOOR, ABS_SUGGEST_FLOOR = 0.40, 0.30
# The self-calibrated mean is meaningless when no member has a usable vector;
# below this it reads as degenerate and routing fails closed.
MIN_USABLE_MEAN = 0.05
ANCHOR_MARGIN = 0.20
ANCHOR_DF_MAX, STRONG_DF_MAX = 0.15, 0.06
ADJUDICATION_MODEL = "gpt-4.1-mini"
# Per scan (folder creation / rescan): at most this many fresh LLM verdicts.
# Cached verdicts are free and don't count.
MAX_SCAN_ADJUDICATIONS = 20
MAX_REJECTION_EXAMPLES = 5
EMB_OBJECT_TYPE = "folder_reel"
TEXT_EMB_OBJECT_TYPE = "folder_text"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "how",
    "i", "in", "is", "it", "me", "my", "of", "on", "or", "that", "the", "to",
    "was", "what", "when", "where", "which", "with", "you", "your", "reels",
    "reel", "about", "recurring", "themes", "common", "folder",
}


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").casefold())
            if len(t) > 2 and t not in STOPWORDS]


# ---------- reel content + embeddings ----------

_JUNK_SUMMARY_MARKERS = (
    "could not be processed", "processing error", "processing failed", "failed reels",
)


def _clean_summary(text) -> str:
    """Drop the pipeline's failure placeholders — embedding 'this reel could
    not be processed' would poison the fingerprint. Applied to item names and
    categories too: 11 'Processing Failed' reels once embedded near-identically
    and outranked every real reel in a folder scan."""
    value = str(text or "").strip()
    return "" if any(m in value.lower() for m in _JUNK_SUMMARY_MARKERS) else value


def _reel_text(row: dict) -> str:
    """High-signal 'what this reel is' text for embedding, from prod fields."""
    doc = {}
    if row.get("document_json"):
        try:
            doc = json.loads(row["document_json"])
        except Exception:
            doc = {}
    item_name = _clean_summary(row.get("item_name"))
    summary = _clean_summary(row.get("summary"))
    # Lead with the "what is this reel actually about" fields (main subject,
    # item, topic) so routing keys on the subject, not incidental details.
    parts = [
        doc.get("main_subject"),
        item_name,
        doc.get("primary_topic"),
        _clean_summary(row.get("primary_category")), _clean_summary(row.get("specific_category")),
        _join(doc.get("subtopics")), _join(doc.get("entities")),
        summary,
        _join(_loads(row.get("canonical_entities_json"))),
        _join(_loads(row.get("canonical_subdomains_json"))),
        doc.get("visual_summary"),
    ]
    if not item_name and not summary:
        # Half-extracted reel (pipeline failure left only the visual pass):
        # fall back to the raw fields deep search matches on, so the reel is
        # not invisible to folder routing while it awaits reprocessing.
        parts += [
            _join(doc.get("visible_text"))[:500],
            str(doc.get("caption") or "")[:600],
            str(doc.get("transcript") or "")[:1500],
        ]
    return "\n".join(str(p).strip() for p in parts if p and str(p).strip())


def _text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()[:16]


def _join(v) -> str:
    if not v:
        return ""
    if isinstance(v, str):
        return v
    return ", ".join(str(x) for x in v if str(x).strip())


def _loads(text):
    try:
        return json.loads(text) if text else []
    except Exception:
        return []


def _reel_rows(conn, user_id: str) -> dict[str, dict]:
    """All of a user's reels with the fields routing needs."""
    rows = conn.execute(
        """
        SELECT r.id AS reel_id,
               COALESCE(ri.item_name, rif.item_name, '') AS item_name,
               COALESCE(ri.summary, rif.summary, '') AS summary,
               COALESCE(ri.primary_category, rif.primary_category, '') AS primary_category,
               COALESCE(ri.secondary_category, rif.specific_category, '') AS specific_category,
               rif.canonical_entities_json, rif.canonical_subdomains_json,
               dsd.document_json
        FROM reels r
        LEFT JOIN reel_items ri ON ri.reel_id = r.id
        LEFT JOIN reel_item_features rif ON rif.reel_id = r.id
        LEFT JOIN deep_search_documents dsd ON dsd.reel_id = r.id
        WHERE r.user_id = ?
        GROUP BY r.id
        """,
        (user_id,),
    ).fetchall()
    return {row["reel_id"]: dict(row) for row in rows}


def _store_vector(conn, reel_id: str, vector: list[float], thash: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO embedding_store "
        "(object_type, object_id, model, version, vector_json, source_text_hash, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (EMB_OBJECT_TYPE, reel_id, EMBEDDING_MODEL, "v2",
         json.dumps(vector), thash, _now(), _now()),
    )


def _cached_vector(conn, reel_id: str):
    return conn.execute(
        "SELECT vector_json, source_text_hash FROM embedding_store "
        "WHERE object_type=? AND object_id=? AND model=? AND version='v2'",
        (EMB_OBJECT_TYPE, reel_id, EMBEDDING_MODEL),
    ).fetchone()


def _warm_vectors(conn, rows: dict[str, dict]) -> None:
    """Batch-embed every reel whose cached vector is missing OR whose content
    changed since it was fingerprinted (source_text_hash mismatch — e.g. a
    half-extracted reel that got reprocessed). One API call per ~96 reels.
    reel_vector() falls back per-reel if this fails, so errors are safe."""
    stale = []
    for rid, row in rows.items():
        text = _reel_text(row)
        thash = _text_hash(text)
        cached = _cached_vector(conn, rid)
        if not cached or cached["source_text_hash"] != thash:
            stale.append((rid, text, thash))
    if not stale:
        return
    try:
        from api_config import get_openai_client

        client = get_openai_client()
        for i in range(0, len(stale), 96):
            chunk = stale[i:i + 96]
            texts = [(text or "empty")[:6000] for _, text, _ in chunk]
            resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
            for (rid, _text, thash), item in zip(chunk, resp.data):
                _store_vector(conn, rid, l2_normalize(item.embedding), thash)
    except Exception:
        pass


def reel_vector(conn, reel_id: str, row: dict) -> list[float] | None:
    """Cached folder embedding for a reel, recomputed when the reel's content
    changes (hash mismatch). Returns the stale vector if a fresh embed fails,
    and None only when no meaningful vector can be produced at all."""
    text = _reel_text(row)
    thash = _text_hash(text)
    cached = _cached_vector(conn, reel_id)
    if cached and cached["source_text_hash"] == thash:
        return json.loads(cached["vector_json"])
    vector, model = embed_text(text)
    if model != EMBEDDING_MODEL:  # embed failed / deterministic fallback
        return json.loads(cached["vector_json"]) if cached else None
    _store_vector(conn, reel_id, vector, thash)
    return vector


# ---------- profile ----------

def _blend(*weighted) -> list[float]:
    acc = None
    for w, vec in weighted:
        if not vec:
            continue
        if acc is None:
            acc = [0.0] * len(vec)
        if len(vec) != len(acc):
            continue  # never mix embedding spaces (96-dim fallback vs 1536 real)
        for i, x in enumerate(vec):
            acc[i] += w * x
    return l2_normalize(acc) if acc else []


def _text_vector(conn, text: str) -> list[float]:
    """Real-model embedding for folder text (description/query), cached by
    content hash. NEVER returns a deterministic fallback — a garbage
    description vector poisons the whole profile and made one folder suggest
    random reels. Empty result means 'no meaningful vector available'."""
    value = (text or "").strip()
    if not value:
        return []
    thash = _text_hash(value)
    cached = conn.execute(
        "SELECT vector_json FROM embedding_store "
        "WHERE object_type=? AND object_id=? AND model=? AND version='v2'",
        (TEXT_EMB_OBJECT_TYPE, thash, EMBEDDING_MODEL),
    ).fetchone()
    if cached:
        return json.loads(cached["vector_json"])
    vector, model = embed_text(value)
    if model != EMBEDDING_MODEL:
        return []
    conn.execute(
        "INSERT OR REPLACE INTO embedding_store "
        "(object_type, object_id, model, version, vector_json, source_text_hash, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (TEXT_EMB_OBJECT_TYPE, thash, EMBEDDING_MODEL, "v2",
         json.dumps(vector), thash, _now(), _now()),
    )
    return vector


def _profile_basis(folder: dict, member_ids: list[str]) -> str:
    basis = f"{folder['name']}::{folder['description']}::{folder.get('query','')}::{','.join(sorted(member_ids))}"
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


def compute_profile(conn, folder: dict, rows: dict) -> tuple[list[float], list[float], list[float]]:
    desc_v = _text_vector(conn, folder["description"])
    query_v = _text_vector(conn, folder.get("query") or folder["name"])
    member_vecs = [v for v in (reel_vector(conn, m, rows[m]) for m in folder["member_ids"] if m in rows) if v]
    centroid = _mean(member_vecs) if member_vecs else desc_v
    if not desc_v and not member_vecs:
        # No meaningful signal at all (embeddings down, nothing cached):
        # fail closed — an empty profile routes nothing, instead of routing noise.
        return [], desc_v, query_v
    profile = _blend((W_DESC, desc_v), (W_QUERY, query_v), (W_CENTROID, centroid))
    return profile, desc_v, query_v


def _mean(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    acc = [0.0] * len(vectors[0])
    for v in vectors:
        for i, x in enumerate(v):
            acc[i] += x
    return l2_normalize([x / len(vectors) for x in acc])


def _member_stats(conn, folder: dict, rows: dict, desc_v, query_v) -> tuple[float, float]:
    """Leave-one-out member similarity (each member scored vs a profile built
    without itself) — otherwise a member inflates its own profile."""
    members = [m for m in folder["member_ids"] if m in rows]
    vecs = {m: reel_vector(conn, m, rows[m]) for m in members}
    members = [m for m in members if vecs.get(m)]
    sims = []
    for m in members:
        others = [vecs[o] for o in members if o != m]
        centroid = _mean(others) if others else []
        prof = _blend((W_DESC, desc_v), (W_QUERY, query_v), (W_CENTROID, centroid))
        sims.append(cosine_similarity(prof, vecs[m]))
    if not sims:
        return 0.0, 0.0
    mean = sum(sims) / len(sims)
    std = math.sqrt(sum((s - mean) ** 2 for s in sims) / len(sims))
    return mean, std


# ---------- anchors ----------

def _anchors(folder: dict, rows: dict) -> tuple[set[str], set[str]]:
    df: dict[str, int] = {}
    identity = {}
    for rid, row in rows.items():
        text = " ".join([str(row.get("item_name", "")), str(row.get("primary_category", "")),
                         str(row.get("specific_category", "")), _join(_loads(row.get("canonical_entities_json")))])
        identity[rid] = text.casefold()
        for tok in set(_tokens(text)):
            df[tok] = df.get(tok, 0) + 1
    n = max(len(rows), 1)
    toks = set(_tokens(f"{folder['name']} {folder['description']}"))
    weak = {t for t in toks if df.get(t, 0) / n <= ANCHOR_DF_MAX}
    desc = folder["description"]
    proper = {m.group(0).casefold() for m in re.finditer(r"\b[A-Z][a-z0-9]+", desc)
              if m.start() > 0 and not re.search(r"[.!?]\s*$", desc[:m.start()])}
    strong = {t for t in weak if df.get(t, 0) / n <= STRONG_DF_MAX}
    if proper:
        strong = {t for t in strong if t in proper}
    return strong, weak


# ---------- routing ----------

def evaluate_folder(conn, folder: dict, rows: dict) -> dict:
    _warm_vectors(conn, rows)
    profile, desc_v, query_v = compute_profile(conn, folder, rows)
    strong, weak = _anchors(folder, rows)
    mean, std = _member_stats(conn, folder, rows, desc_v, query_v)
    if not profile or mean <= MIN_USABLE_MEAN:
        # Degenerate calibration (no profile, or no member has a usable
        # vector): thresholds would sit near zero and the whole library would
        # qualify — observed flooding 232 suggestions into one folder. Route
        # nothing until vectors exist; the next scan self-heals via _warm_vectors.
        return {"profile": profile, "candidates": [],
                "thresholds": {"auto": 1.0, "suggest": 1.0}}
    t_auto = max(mean - max(AUTO_MARGIN_SIGMA * std, AUTO_MARGIN_FLOOR), ABS_AUTO_FLOOR)
    t_suggest = max(
        mean - min(max(SUGGEST_MARGIN_SIGMA * std, SUGGEST_MARGIN_FLOOR), SUGGEST_MARGIN_CAP),
        ABS_SUGGEST_FLOOR,
    )
    t_anchor = max(mean - ANCHOR_MARGIN, ABS_SUGGEST_FLOOR)
    member_set = set(folder["member_ids"])

    candidates = []
    for rid, row in rows.items():
        if rid in member_set:
            continue
        vec = reel_vector(conn, rid, row)
        if not vec:
            continue
        sim = cosine_similarity(profile, vec)
        identity = (str(row.get("item_name", "")) + " " + str(row.get("primary_category", "")) + " "
                    + _join(_loads(row.get("canonical_entities_json")))).casefold()
        hit_strong = [a for a in strong if re.search(rf"(?<![a-z0-9]){re.escape(a)}", identity)]
        hit_weak = [a for a in weak if re.search(rf"(?<![a-z0-9]){re.escape(a)}", identity)]
        if sim >= t_auto and (hit_strong or not strong):
            decision = "auto"
        elif sim >= t_suggest:
            decision = "suggest"
        elif hit_weak and sim >= t_anchor:
            decision = "suggest"
        else:
            continue
        candidates.append({"reel_id": rid, "similarity": round(sim, 4), "decision": decision})
    candidates.sort(key=lambda c: -c["similarity"])
    return {"profile": profile, "candidates": candidates,
            "thresholds": {"auto": t_auto, "suggest": t_suggest}}


def _adjudication_hash(folder: dict) -> str:
    """Verdict cache key component: verdicts are only valid for the exact
    folder meaning they were judged against, so a description edit re-opens
    every question."""
    return _text_hash(f"{folder['name']}::{folder['description']}")


def _cached_verdict(conn, folder_id: int, reel_id: str, desc_hash: str) -> str | None:
    row = conn.execute(
        "SELECT verdict FROM folder_adjudications WHERE folder_id=? AND reel_id=? AND desc_hash=?",
        (folder_id, reel_id, desc_hash),
    ).fetchone()
    return row["verdict"] if row else None


def _store_verdict(conn, user_id: str, folder_id: int, reel_id: str, desc_hash: str, verdict: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO folder_adjudications "
        "(user_id, folder_id, reel_id, desc_hash, verdict, created_at) VALUES (?,?,?,?,?,?)",
        (user_id, folder_id, reel_id, desc_hash, verdict, _now()),
    )


def _folder_rejections(conn, folder_id: int) -> list[tuple[str, str]]:
    """Most recent (reel title, user's skip reason) pairs for this folder —
    negative examples that teach the adjudicator where the boundary is."""
    rows = conn.execute(
        """
        SELECT COALESCE(MAX(ri.item_name), fm.reel_id) AS name,
               MAX(fm.reject_reason) AS reason
        FROM folder_memberships fm
        LEFT JOIN reel_items ri ON ri.reel_id = fm.reel_id
        WHERE fm.folder_id=? AND fm.status='rejected'
        GROUP BY fm.reel_id
        ORDER BY MAX(fm.updated_at) DESC LIMIT ?
        """,
        (folder_id, MAX_REJECTION_EXAMPLES),
    ).fetchall()
    return [(str(r["name"] or ""), str(r["reason"] or "")) for r in rows]


def folder_verdict(conn, user_id: str, folder_id: int, folder: dict, row: dict,
                   rejections: list[tuple[str, str]] | None = None) -> str | None:
    """Cached LLM yes/no for 'does this reel belong here'. Fresh verdicts are
    stored; None (LLM unreachable) is never cached so it retries next scan."""
    desc_hash = _adjudication_hash(folder)
    cached = _cached_verdict(conn, folder_id, row.get("reel_id") or "", desc_hash)
    if cached:
        return cached
    if rejections is None:
        rejections = _folder_rejections(conn, folder_id)
    verdict = llm_verdict(folder, row, rejections)
    if verdict in ("yes", "no"):
        _store_verdict(conn, user_id, folder_id, row.get("reel_id") or "", desc_hash, verdict)
    return verdict


def llm_verdict(folder: dict, row: dict, rejections: list[tuple[str, str]] | None = None) -> str | None:
    try:
        from api_config import get_openai_client
        doc = json.loads(row.get("document_json") or "{}")
        client = get_openai_client()
        item_name = str(row.get("item_name") or "").strip()
        summary = _clean_summary(row.get("summary"))[:400]
        extra = ""
        if not item_name and not summary:
            # half-extracted reel — judge from the raw signals instead
            extra = (f"Caption: {str(doc.get('caption') or '')[:300]}\n"
                     f"Transcript: {str(doc.get('transcript') or '')[:500]}\n"
                     f"Visuals: {_join(doc.get('visual_entities'))[:200]}\n")
        rejected_block = ""
        if rejections:
            lines = "\n".join(
                f"- {name or 'a reel'}" + (f' (user said: "{reason}")' if reason else "")
                for name, reason in rejections
            )
            rejected_block = (
                "\nThe user removed these reels from this folder — reels like them "
                "do NOT belong:\n" + lines + "\n"
            )
        prompt = (
            "A user has a folder of saved Instagram reels.\n"
            f"Folder: {folder['name']}\nDescription: {folder['description']}\n"
            + rejected_block +
            "\nA new reel arrived:\n"
            f"Title: {item_name}\nSummary: {summary}\n"
            f"Topic: {doc.get('primary_topic','')}\nEntities: {_join(doc.get('entities'))}\n"
            + extra +
            "\nDoes this reel belong in this folder? The description is the rule: "
            "sharing a place, domain, or one keyword with it is NOT enough — the reel's "
            "actual subject must be what the description asks for. Treat alternate names "
            'for the same thing as matches. Reply JSON only: {"belongs": true/false}'
        )
        resp = client.chat.completions.create(
            model=ADJUDICATION_MODEL, temperature=0, max_tokens=20,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        return "yes" if json.loads(resp.choices[0].message.content).get("belongs") else "no"
    except Exception:
        return None


# ---------- public API ----------

def _folder_dict(row) -> dict:
    d = dict(row)
    d["member_ids"] = []
    return d


def list_folders(user_id: str) -> list[dict]:
    with get_connection() as conn:
        folders = conn.execute(
            "SELECT * FROM user_folders WHERE user_id=? AND is_active=1 ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        out = []
        for f in folders:
            count = conn.execute(
                "SELECT COUNT(*) n FROM folder_memberships WHERE folder_id=? AND status='member'",
                (f["id"],),
            ).fetchone()["n"]
            out.append({"id": f["id"], "name": f["name"], "description": f["description"],
                        "query": f["query"], "item_count": count, "created_at": f["created_at"]})
        return out


def _members(conn, folder_id: int, statuses=("member",)) -> list[str]:
    q = "SELECT reel_id FROM folder_memberships WHERE folder_id=? AND status IN (%s)" % \
        ",".join("?" for _ in statuses)
    return [r["reel_id"] for r in conn.execute(q, (folder_id, *statuses)).fetchall()]


def suggest_meta(user_id: str, query: str, reel_ids: list[str]) -> dict:
    """Draft the folder name/description from the SEARCH PHRASE alone — no LLM.

    The phrase IS the user's intent (someone who wants paneer recipes searches
    "paneer recipes"), so the visible description is a plain template of it:
    instant, free, and 1-2 seconds to edit. The selected reels still shape
    routing silently (member centroid in the profile), and alias/nuance
    matching lives in the routing-time adjudicator — not in the description.
    """
    phrase = (query or "").strip()
    if not phrase:
        return {"name": "New list", "description": "Reels saved to this list.",
                "source": "template"}
    return {"name": phrase.title()[:80],
            "description": f"Reels about {phrase}."[:160],
            "source": "template"}


def create_folder(user_id: str, name: str, description: str, query: str, reel_ids: list[str]) -> dict:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO user_folders (user_id,name,description,query,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (user_id, name.strip(), description.strip(), (query or "").strip(), _now(), _now()),
        )
        fid = cur.lastrowid
        for rid in dict.fromkeys(reel_ids):
            conn.execute(
                "INSERT OR IGNORE INTO folder_memberships (user_id,folder_id,reel_id,source,status,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (user_id, fid, rid, "manual", "member", _now(), _now()),
            )
        _refresh_profile(conn, user_id, fid)
        # One-time scan at birth: reels saved BEFORE this folder existed get a
        # shot at the Suggested tray. After this, only ingest-time routing (and
        # the manual Rescan button) touch memberships — no per-open scanning.
        try:
            frow = conn.execute("SELECT * FROM user_folders WHERE id=?", (fid,)).fetchone()
            _backfill_suggestions(conn, user_id, frow)
        except Exception:
            pass
    return {"id": fid, "name": name, "description": description, "item_count": len(set(reel_ids))}


def _refresh_profile(conn, user_id: str, folder_id: int) -> None:
    frow = conn.execute("SELECT * FROM user_folders WHERE id=?", (folder_id,)).fetchone()
    if not frow:
        return
    folder = {"name": frow["name"], "description": frow["description"], "query": frow["query"],
              "member_ids": _members(conn, folder_id)}
    rows = _reel_rows(conn, user_id)
    profile, _, _ = compute_profile(conn, folder, rows)
    conn.execute(
        "UPDATE user_folders SET profile_vector_json=?, profile_basis=?, updated_at=? WHERE id=?",
        (json.dumps(profile), _profile_basis(folder, folder["member_ids"]), _now(), folder_id),
    )


def _reel_card(conn, reel_id: str) -> dict:
    row = conn.execute(
        "SELECT r.id AS reel_id, r.url, r.thumbnail_path AS thumbnail_path, "
        "r.local_video_path AS local_video_path, COALESCE(ri.item_name,'') item_name, "
        "COALESCE(ri.summary,'') summary, COALESCE(ri.primary_category,'') primary_category "
        "FROM reels r LEFT JOIN reel_items ri ON ri.reel_id=r.id WHERE r.id=? LIMIT 1",
        (reel_id,),
    ).fetchone()
    if not row:
        return {"reel_id": reel_id}
    card = dict(row)
    # Surface served media URLs so folder cards render real thumbnails/video,
    # matching the rest of the app. Never let media-URL generation (e.g. R2
    # misconfig) take down the folder view — cards degrade to no thumbnail.
    try:
        card["thumbnail_url"] = _media_url_from_path(card.get("thumbnail_path") or "")
        card["local_video_url"] = _media_url_from_path(card.get("local_video_path") or "")
    except Exception:
        card["thumbnail_url"] = ""
        card["local_video_url"] = ""
    return card


def _backfill_suggestions(conn, user_id: str, folder_row) -> None:
    """Self-healing scan: score the user's whole library against this folder and
    insert anything that matches as a 'suggested' membership. Catches reels the
    ingest-time hook missed (worker timing, failures, reels saved before the
    folder existed). Reels already decided — member, suggested, or rejected —
    are never touched, so a user's "No" stays a No.

    Every candidate must get an LLM 'yes' before entering the tray: embeddings
    alone can't tell chest-workout from bicep-curl or eating-in-Bali from
    Bali-belly-remedy. No verdict (LLM down) = not inserted, retried next scan."""
    folder = {"name": folder_row["name"], "description": folder_row["description"],
              "query": folder_row["query"],
              "member_ids": _members(conn, folder_row["id"])}
    rows = _reel_rows(conn, user_id)
    decided = {r["reel_id"] for r in conn.execute(
        "SELECT reel_id FROM folder_memberships WHERE folder_id=?", (folder_row["id"],))}
    ev = evaluate_folder(conn, folder, rows)
    rejections = _folder_rejections(conn, folder_row["id"])
    desc_hash = _adjudication_hash(folder)
    fresh_calls = 0
    for cand in ev["candidates"]:
        if cand["reel_id"] in decided:
            continue
        verdict = _cached_verdict(conn, folder_row["id"], cand["reel_id"], desc_hash)
        if verdict is None:
            if fresh_calls >= MAX_SCAN_ADJUDICATIONS:
                continue  # candidates are sorted by similarity; the tail can wait
            fresh_calls += 1
            verdict = llm_verdict(folder, rows[cand["reel_id"]], rejections)
            if verdict in ("yes", "no"):
                _store_verdict(conn, user_id, folder_row["id"], cand["reel_id"], desc_hash, verdict)
        if verdict != "yes":
            continue
        conn.execute(
            "INSERT OR IGNORE INTO folder_memberships "
            "(user_id, folder_id, reel_id, source, status, score, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, folder_row["id"], cand["reel_id"], "backfill", "suggested",
             cand["similarity"], _now(), _now()),
        )


def _prune_suggestions(conn, user_id: str, folder_row) -> None:
    """Re-vet the existing Suggested tray against the current description.

    Two passes: (1) free — drop suggestions whose similarity no longer clears
    the suggest band (cleans trays polluted before the floors existed);
    (2) adjudicated — drop survivors the LLM says don't belong. Rows are
    DELETED, not marked rejected: the user never decided, so a future profile
    may legitimately re-suggest them."""
    folder = {"name": folder_row["name"], "description": folder_row["description"],
              "query": folder_row["query"],
              "member_ids": _members(conn, folder_row["id"])}
    rows = _reel_rows(conn, user_id)
    ev = evaluate_folder(conn, folder, rows)
    if not ev["profile"]:
        return  # embeddings unavailable: leave the tray alone rather than guess
    t_suggest = ev["thresholds"]["suggest"]
    suggested = [r["reel_id"] for r in conn.execute(
        "SELECT reel_id FROM folder_memberships WHERE folder_id=? AND status='suggested'",
        (folder_row["id"],))]
    rejections = _folder_rejections(conn, folder_row["id"])
    desc_hash = _adjudication_hash(folder)
    fresh_calls = 0
    for rid in suggested:
        row = rows.get(rid)
        vec = reel_vector(conn, rid, row) if row else None
        sim = cosine_similarity(ev["profile"], vec) if vec else 0.0
        verdict = None
        if row is None or not vec or sim < t_suggest:
            verdict = "no"
        else:
            verdict = _cached_verdict(conn, folder_row["id"], rid, desc_hash)
            if verdict is None and fresh_calls < MAX_SCAN_ADJUDICATIONS:
                fresh_calls += 1
                verdict = llm_verdict(folder, row, rejections)
                if verdict in ("yes", "no"):
                    _store_verdict(conn, user_id, folder_row["id"], rid, desc_hash, verdict)
        if verdict == "no":
            conn.execute(
                "DELETE FROM folder_memberships WHERE folder_id=? AND reel_id=? AND status='suggested'",
                (folder_row["id"], rid),
            )


def rescan_folder(user_id: str, folder_id: int) -> dict | None:
    """Manual re-scan (Rescan button / after a description edit): prune the
    Suggested tray of anything that no longer belongs, then score the library
    for new suggestions. Routing otherwise happens only at ingest + once at
    folder creation — no per-open scanning."""
    with get_connection() as conn:
        f = conn.execute(
            "SELECT * FROM user_folders WHERE id=? AND user_id=? AND is_active=1",
            (folder_id, user_id),
        ).fetchone()
        if not f:
            return None
        _prune_suggestions(conn, user_id, f)
        _backfill_suggestions(conn, user_id, f)
    return folder_detail(user_id, folder_id)


def folder_detail(user_id: str, folder_id: int) -> dict | None:
    with get_connection() as conn:
        f = conn.execute(
            "SELECT * FROM user_folders WHERE id=? AND user_id=? AND is_active=1",
            (folder_id, user_id),
        ).fetchone()
        if not f:
            return None
        members = [dict(_reel_card(conn, m["reel_id"]), source=m["source"]) for m in conn.execute(
            "SELECT fm.reel_id, fm.source FROM folder_memberships fm "
            "LEFT JOIN reels r ON r.id = fm.reel_id "
            "WHERE fm.folder_id=? AND fm.status='member' "
            "ORDER BY r.received_at DESC",
            (folder_id,))]
        suggestions = [_reel_card(conn, m["reel_id"]) for m in conn.execute(
            "SELECT reel_id FROM folder_memberships WHERE folder_id=? AND status='suggested' "
            "ORDER BY score DESC", (folder_id,))]
        return {"id": f["id"], "name": f["name"], "description": f["description"],
                "query": f["query"], "members": members, "suggestions": suggestions}


def set_membership_status(user_id: str, folder_id: int, reel_id: str, status: str,
                          reason: str = "") -> dict:
    """Accept/reject a suggestion. For rejections, `reason` is the user's
    optional "why I skipped this" — it becomes a negative example in future
    adjudications, so every explained Skip tightens the folder."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE folder_memberships SET status=?, source='manual', reject_reason=?, updated_at=? "
            "WHERE folder_id=? AND reel_id=? AND user_id=?",
            (status, (reason or "").strip()[:200] if status == "rejected" else "",
             _now(), folder_id, reel_id, user_id),
        )
        if status == "member":
            _refresh_profile(conn, user_id, folder_id)
    return {"ok": True, "folder_id": folder_id, "reel_id": reel_id, "status": status}


def delete_folder(user_id: str, folder_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE user_folders SET is_active=0, updated_at=? WHERE id=? AND user_id=?",
                     (_now(), folder_id, user_id))


def route_reel(user_id: str, reel_id: str, adjudicate: bool = True) -> list[dict]:
    """Score one new reel against all the user's folders. Returns per-folder
    decisions (auto/suggest) and writes suggested/auto memberships.

    Nothing enters a folder — not even the Suggested tray — without an LLM
    'yes' (cached per description). LLM unreachable = reel skipped; the next
    manual rescan retries it."""
    with get_connection() as conn:
        rows = _reel_rows(conn, user_id)
        if reel_id not in rows:
            return []
        results = []
        folders = conn.execute(
            "SELECT * FROM user_folders WHERE user_id=? AND is_active=1", (user_id,)
        ).fetchall()
        for frow in folders:
            folder = {"name": frow["name"], "description": frow["description"], "query": frow["query"],
                      "member_ids": _members(conn, frow["id"])}
            already = conn.execute(
                "SELECT status FROM folder_memberships WHERE folder_id=? AND reel_id=?",
                (frow["id"], reel_id),
            ).fetchone()
            if already:
                continue
            ev = evaluate_folder(conn, folder, rows)
            match = next((c for c in ev["candidates"] if c["reel_id"] == reel_id), None)
            if not match:
                continue
            decision = match["decision"]
            if adjudicate:
                verdict = folder_verdict(conn, user_id, frow["id"], folder, rows[reel_id])
                if verdict != "yes":
                    continue
            status = "member" if decision == "auto" else "suggested"
            conn.execute(
                "INSERT OR IGNORE INTO folder_memberships (user_id,folder_id,reel_id,source,status,score,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (user_id, frow["id"], reel_id, "auto", status, match["similarity"], _now(), _now()),
            )
            if status == "member":
                _refresh_profile(conn, user_id, frow["id"])
            results.append({"folder_id": frow["id"], "folder": frow["name"],
                            "decision": decision, "similarity": match["similarity"]})
        return results
