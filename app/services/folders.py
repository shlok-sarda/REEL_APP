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
    (mean - k*sigma), because absolute cosine scale is not comparable.
  * pure similarity cannot separate "same template, different subject", so
    AUTO additionally requires a rare-term ANCHOR hit when the folder has any.
  * the SUGGEST band is adjudicated by a cheap LLM yes/no, cached per description.

Reel embeddings are computed from the deep-search document text and cached in
embedding_store (object_type='folder_reel'); we never use deterministic-fallback
vectors for routing (they carry no meaning).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time

from app.db.database import get_connection
from app.services.personalization_v2.embeddings import (
    EMBEDDING_MODEL,
    cosine_similarity,
    embed_text,
    l2_normalize,
)

W_DESC, W_QUERY, W_CENTROID = 0.45, 0.05, 0.50
AUTO_MARGIN_SIGMA, AUTO_MARGIN_FLOOR = 1.0, 0.05
SUGGEST_MARGIN_SIGMA, SUGGEST_MARGIN_FLOOR = 2.0, 0.10
ANCHOR_MARGIN = 0.20
ANCHOR_DF_MAX, STRONG_DF_MAX = 0.15, 0.06
ADJUDICATION_MODEL = SUGGESTION_MODEL = "gpt-4.1-mini"
EMB_OBJECT_TYPE = "folder_reel"

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

def _reel_text(row: dict) -> str:
    """High-signal 'what this reel is' text for embedding, from prod fields."""
    doc = {}
    if row.get("document_json"):
        try:
            doc = json.loads(row["document_json"])
        except Exception:
            doc = {}
    parts = [
        row.get("item_name"), row.get("summary"),
        row.get("primary_category"), row.get("specific_category"),
        doc.get("main_subject"), doc.get("primary_topic"),
        _join(doc.get("subtopics")), _join(doc.get("entities")),
        _join(_loads(row.get("canonical_entities_json"))),
        _join(_loads(row.get("canonical_subdomains_json"))),
        doc.get("visual_summary"),
    ]
    return "\n".join(str(p).strip() for p in parts if p and str(p).strip())


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


def reel_vector(conn, reel_id: str, row: dict) -> list[float] | None:
    """Get cached folder embedding for a reel, or compute it. Returns None if we
    could only get a deterministic fallback (no meaning -> unroutable)."""
    cached = conn.execute(
        "SELECT vector_json, model FROM embedding_store "
        "WHERE object_type=? AND object_id=? AND model=? AND version='v1'",
        (EMB_OBJECT_TYPE, reel_id, EMBEDDING_MODEL),
    ).fetchone()
    if cached:
        return json.loads(cached["vector_json"])
    vector, model = embed_text(_reel_text(row))
    if model != EMBEDDING_MODEL:  # deterministic-fallback -> don't cache/route
        return None
    conn.execute(
        "INSERT OR REPLACE INTO embedding_store "
        "(object_type, object_id, model, version, vector_json, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (EMB_OBJECT_TYPE, reel_id, EMBEDDING_MODEL, "v1", json.dumps(vector), _now(), _now()),
    )
    return vector


# ---------- profile ----------

def _blend(*weighted) -> list[float]:
    acc = None
    for w, vec in weighted:
        if not vec:
            continue
        if acc is None:
            acc = [0.0] * len(vec)
        for i, x in enumerate(vec):
            acc[i] += w * x
    return l2_normalize(acc) if acc else []


def _profile_basis(folder: dict, member_ids: list[str]) -> str:
    basis = f"{folder['name']}::{folder['description']}::{folder.get('query','')}::{','.join(sorted(member_ids))}"
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


def compute_profile(conn, folder: dict, rows: dict) -> tuple[list[float], list[float], list[float]]:
    desc_v, _ = embed_text(folder["description"])
    query_v, _ = embed_text(folder.get("query") or folder["name"])
    member_vecs = [v for v in (reel_vector(conn, m, rows[m]) for m in folder["member_ids"] if m in rows) if v]
    centroid = _mean(member_vecs) if member_vecs else desc_v
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
    profile, desc_v, query_v = compute_profile(conn, folder, rows)
    strong, weak = _anchors(folder, rows)
    mean, std = _member_stats(conn, folder, rows, desc_v, query_v)
    t_auto = mean - max(AUTO_MARGIN_SIGMA * std, AUTO_MARGIN_FLOOR)
    t_suggest = mean - max(SUGGEST_MARGIN_SIGMA * std, SUGGEST_MARGIN_FLOOR)
    t_anchor = mean - ANCHOR_MARGIN
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


def llm_verdict(folder: dict, row: dict) -> str | None:
    try:
        from api_config import get_openai_client
        doc = json.loads(row.get("document_json") or "{}")
        client = get_openai_client()
        prompt = (
            "A user has a folder of saved Instagram reels.\n"
            f"Folder: {folder['name']}\nDescription: {folder['description']}\n\n"
            "A new reel arrived:\n"
            f"Title: {row.get('item_name','')}\nSummary: {str(row.get('summary',''))[:400]}\n"
            f"Topic: {doc.get('primary_topic','')}\nEntities: {_join(doc.get('entities'))}\n\n"
            "Does this reel belong in this folder? Treat alternate names for the same "
            'thing as matches. Reply JSON only: {"belongs": true/false}'
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
    """LLM-draft a folder name + content-driven description (name low-weight)."""
    with get_connection() as conn:
        rows = _reel_rows(conn, user_id)
    items = [rows[r] for r in reel_ids if r in rows]
    lines = []
    for r in items[:12]:
        doc = json.loads(r.get("document_json") or "{}")
        lines.append(f"- {r.get('item_name','')} | topic: {doc.get('primary_topic','')} "
                     f"| entities: {_join(doc.get('entities'))[:60]}")
    try:
        from api_config import get_openai_client
        client = get_openai_client()
        prompt = (
            "The user searched their saved reels for a phrase, selected some results, and is "
            "creating a folder from them.\n\n"
            f'Search phrase (their intent): "{query}"\n\nSelected reels:\n' + "\n".join(lines) + "\n\n"
            "Write a folder name and a 1-2 sentence description.\n"
            "- The SEARCH PHRASE is the user's intent and DOMINATES the meaning (~70%). Build the "
            "description around it.\n"
            "- Use the selected reels only to SHARPEN the phrase — the specific place, activity, or "
            "theme they have in common (e.g. phrase 'things to do in Varanasi' + restaurant reels "
            "-> a Varanasi food/restaurants folder).\n"
            "- If it's about a specific place/brand, include common alternate names/spellings.\n"
            "- Write the description like a rule for what belongs in this folder going forward. "
            "No emojis/hashtags.\n"
            'Reply JSON only: {"name":"...","description":"..."}'
        )
        resp = client.chat.completions.create(
            model=SUGGESTION_MODEL, temperature=0.2, max_tokens=160,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(resp.choices[0].message.content)
        name, desc = str(data.get("name", "")).strip(), str(data.get("description", "")).strip()
        if name and desc:
            return {"name": name[:80], "description": desc[:500], "source": "llm"}
    except Exception:
        pass
    return {"name": (query or "New list").strip()[:80],
            "description": f"Reels about {query}.", "source": "fallback"}


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
        "SELECT r.id AS reel_id, r.url, COALESCE(ri.item_name,'') item_name, "
        "COALESCE(ri.summary,'') summary, COALESCE(ri.primary_category,'') primary_category "
        "FROM reels r LEFT JOIN reel_items ri ON ri.reel_id=r.id WHERE r.id=? LIMIT 1",
        (reel_id,),
    ).fetchone()
    return dict(row) if row else {"reel_id": reel_id}


def folder_detail(user_id: str, folder_id: int) -> dict | None:
    with get_connection() as conn:
        f = conn.execute(
            "SELECT * FROM user_folders WHERE id=? AND user_id=? AND is_active=1",
            (folder_id, user_id),
        ).fetchone()
        if not f:
            return None
        members = [dict(_reel_card(conn, r), source=s) for r, s in
                   [(m["reel_id"], m["source"]) for m in conn.execute(
                       "SELECT reel_id, source FROM folder_memberships WHERE folder_id=? AND status='member'",
                       (folder_id,))]]
        suggestions = [_reel_card(conn, m["reel_id"]) for m in conn.execute(
            "SELECT reel_id FROM folder_memberships WHERE folder_id=? AND status='suggested'", (folder_id,))]
        return {"id": f["id"], "name": f["name"], "description": f["description"],
                "query": f["query"], "members": members, "suggestions": suggestions}


def set_membership_status(user_id: str, folder_id: int, reel_id: str, status: str) -> dict:
    with get_connection() as conn:
        conn.execute(
            "UPDATE folder_memberships SET status=?, source='manual', updated_at=? "
            "WHERE folder_id=? AND reel_id=? AND user_id=?",
            (status, _now(), folder_id, reel_id, user_id),
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
    decisions (auto/suggest) and writes suggested/auto memberships."""
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
            if decision == "auto" and adjudicate:
                v = llm_verdict(folder, rows[reel_id])
                if v == "no":
                    decision = "suggest"
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
