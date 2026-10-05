"""Search report: one AI read across the reels a search returned.

The user searches ("things to do in Varanasi"), taps Report, and gets what
they would otherwise piece together by opening every reel: the places, dishes,
techniques, tips, each point linked back to the reel it came from.

Relevance is decided by the model in the same call that writes the report.
Search ranking can't make that call on its own: the gate calibration in
deep_search_hybrid.py measured true matches as low as 0.16 cosine and
off-topic tops at 0.27, so no score cutoff or fixed top-N separates them.
The model reads every candidate anyway, so dropping the off-topic ones costs
nothing extra. The user can still override it (include / exclude), which
changes the cache key and regenerates.

Admin-only while the founder tries it. Reports are cached by query + the
exact reel set, so reopening one never pays twice; fresh generations are
capped per user per day.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from app.db.database import get_connection

REPORT_MODEL = "gpt-4.1-mini"
PROMPT_VERSION = "v4"
MAX_CANDIDATES = 20
DAILY_GENERATIONS = 20

# Per-field character budgets. A fully processed reel measured ~450 tokens
# median / ~860 p90 across these fields (local library, 2026-10-05); the caps
# only bite on the long tail (rambling transcripts, essay captions).
FIELD_LIMITS = {
    "transcript": 1800,
    "caption": 600,
    "visible_text": 400,
    "visual_summary": 400,
    "item_summaries": 500,
}


class ReportError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _norm(text: Any) -> str:
    return " ".join(str(text or "").split())


def _joined(value: Any, limit: int = 0) -> str:
    if isinstance(value, list):
        text = " | ".join(_norm(v) for v in value if _norm(v))
    else:
        text = _norm(value)
    return text[:limit] if limit else text


def search_report_enabled(user_id: str) -> bool:
    """Admin accounts only (settings.admin_emails, founder always included)."""
    from app.config import settings

    if not user_id:
        return False
    with get_connection() as conn:
        row = conn.execute(
            "SELECT lower(email) AS email FROM users WHERE id = ? LIMIT 1", (user_id,)
        ).fetchone()
    email = (row["email"] or "") if row else ""
    return bool(email) and email in settings.admin_emails


def _reel_block(label: str, doc: dict, picked: bool) -> str:
    lines = [f"[{label}]" + (" (USER PICKED)" if picked else "")]
    fields = [
        ("subject", _joined(doc.get("main_subject"))),
        ("title", _joined(doc.get("item_names"))),
        ("places", _joined(doc.get("locations"))),
        ("mentions", _joined((doc.get("entities") or [])[:10])),
        ("summary", _joined(doc.get("item_summaries"), FIELD_LIMITS["item_summaries"])),
        ("on screen", _joined(doc.get("visible_text"), FIELD_LIMITS["visible_text"])),
        ("visual", _joined(doc.get("visual_summary"), FIELD_LIMITS["visual_summary"])),
        ("caption", _joined(doc.get("caption"), FIELD_LIMITS["caption"])),
        ("speech", _joined(doc.get("transcript"), FIELD_LIMITS["transcript"])),
    ]
    lines += [f"{name}: {text}" for name, text in fields if text]
    return "\n".join(lines)


def _prompt(query: str, blocks: list[str]) -> str:
    return (
        f'The person searched their saved Instagram reels for: "{query}"\n\n'
        "Below are the reels that search returned, best match first. Search is "
        "loose, so some of them are only loosely related or off-topic.\n\n"
        "1. First judge every reel on its own: would someone who searched this "
        "want what this reel says in their answer? It helps only if it contains "
        "something specific that answers the search. Mentioning the same topic, "
        "word, city or vibe without answering it does not count (someone talking "
        "about their commute is not a driving tip). Judge each reel the same way no matter "
        "which other reels are in the list.\n"
        "2. Using ONLY the reels you judged helpful, write a report that gives the person what they were looking for, so "
        "they don't have to open each reel. Pull out the concrete specifics: "
        "names of places, dishes, products, techniques, prices, steps, tips, "
        "warnings. Merge duplicates across reels. Group points into 2-6 sections "
        "whose headings fit this particular search.\n"
        '3. Every point must cite the reel(s) it came from by label, like "R3". '
        "Never state anything the reels don't say. No filler or generic advice "
        "(\"try it for a complete experience\"): every point is a specific fact a "
        "reel states or shows. Never say the same fact twice in different words; "
        "a reel with one useful fact gets one point. "
        "Speech-to-text can be garbled Hindi/Hinglish: use only what is clear.\n\n"
        "Reels marked (USER PICKED) were chosen by the person: judge them helpful.\n\n"
        "Return JSON, with the per-reel verdicts first:\n"
        '{"reels": [{"ref": "R1", "helps": true, "why": "<a few words>"}], '
        '"title": "<short report title>", '
        '"summary": "<1-2 sentence overview of what the reels say>", '
        '"sections": [{"heading": "<section heading>", '
        '"points": [{"text": "<one specific point, under 25 words>", "refs": ["R1"]}]}], '
        '"gaps": "<one sentence on what these reels do not cover, or empty>"}\n'
        "List every reel in \"reels\". At most 8 points per section. If no reel "
        "helps, return \"sections\": [].\n\n"
        "REELS:\n\n" + "\n\n".join(blocks)
    )


def _cache_key(user_id: str, query: str, candidate_ids: list[str], include: set[str]) -> str:
    raw = json.dumps(
        [PROMPT_VERSION, REPORT_MODEL, user_id, query.lower(), candidate_ids, sorted(include)],
        separators=(",", ":"),
    )
    return hashlib.sha1(raw.encode()).hexdigest()


def _generations_today(user_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM search_reports WHERE user_id = ? AND created_at >= ?",
            (user_id, time.strftime("%Y-%m-%d") + " 00:00:00"),
        ).fetchone()
    return int(row["n"] or 0)


def _call_model(prompt: str) -> tuple[dict, dict]:
    from api_config import get_openai_client

    client = get_openai_client()
    resp = client.chat.completions.create(
        model=REPORT_MODEL,
        messages=[
            {"role": "system", "content": "You write short, specific reports from a person's saved Instagram reels, using only what the reels contain."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    usage = {
        "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(resp.usage, "completion_tokens", 0) or 0,
    }
    return json.loads(resp.choices[0].message.content or "{}"), usage


def _clean_report(raw: dict, label_to_id: dict[str, str], picked: set[str]) -> dict:
    """Keep only points that cite a reel the model itself judged helpful (or
    the user picked). A point with no such source is either unsourced or
    leaning on a reel the verdict already rejected, so it gets dropped. The
    verdicts come first in the JSON so the model commits to them before it
    writes, which is what keeps the same reel from flipping between runs."""
    helpful = set(picked)
    skipped_why = {}
    for verdict in raw.get("reels") or []:
        if not isinstance(verdict, dict):
            continue
        rid = label_to_id.get(_norm(verdict.get("ref")).upper())
        if not rid:
            continue
        if verdict.get("helps") is True:
            helpful.add(rid)
        elif rid not in picked:
            skipped_why[rid] = _norm(verdict.get("why"))
    sections = []
    for section in raw.get("sections") or []:
        if not isinstance(section, dict):
            continue
        points = []
        for point in section.get("points") or []:
            if not isinstance(point, dict):
                continue
            text = _norm(point.get("text"))
            refs = []
            for ref in point.get("refs") or []:
                rid = label_to_id.get(_norm(ref).upper())
                if rid in helpful and rid not in refs:
                    refs.append(rid)
            if text and refs:
                points.append({"text": text, "reel_ids": refs})
        heading = _norm(section.get("heading"))
        if points:
            sections.append({"heading": heading, "points": points})
    return {
        "title": _norm(raw.get("title")),
        "summary": _norm(raw.get("summary")),
        "gaps": _norm(raw.get("gaps")),
        "sections": sections,
        "skipped_why": skipped_why,
    }


def _payload(report: dict, candidate_ids: list[str], excluded: list[str], docs: dict, query: str, cached: bool, usage: dict) -> dict:
    from app.services.deep_search import _result_payload

    used: list[str] = []
    for section in report["sections"]:
        for point in section["points"]:
            for rid in point["reel_ids"]:
                if rid not in used:
                    used.append(rid)
    # Number cited reels in search-rank order so [1] is the best match.
    used.sort(key=lambda rid: candidate_ids.index(rid) if rid in candidate_ids else len(candidate_ids))
    number = {rid: i + 1 for i, rid in enumerate(used)}
    for section in report["sections"]:
        for point in section["points"]:
            point["refs"] = sorted(number[rid] for rid in point["reel_ids"])

    def reel(rid: str, why: str = "") -> dict:
        item = _result_payload(docs[rid], 0, [])
        if why:
            item["why"] = why
        return item

    skipped = [
        reel(rid, report["skipped_why"].get(rid) or "Not about this search")
        for rid in candidate_ids if rid not in number and rid in docs
    ] + [reel(rid, "Removed by you") for rid in excluded if rid in docs]
    return {
        "status": "ok" if report["sections"] else "no_match",
        "query": query,
        "title": (report["title"] if report["sections"] else "") or query,
        # With nothing usable, the model's summary/gaps describe the rejected
        # reels ("potentially useful for…") and contradict the empty state.
        "summary": report["summary"] if report["sections"] else "",
        "gaps": report["gaps"] if report["sections"] else "",
        "sections": report["sections"],
        "used": [reel(rid) for rid in used if rid in docs],
        "skipped": skipped,
        "cached": cached,
        "usage": usage,
    }


def build_search_report(
    user_id: str,
    query: str,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> dict:
    from app.services.deep_search import load_deep_search_documents, search_user_documents

    query = _norm(query)[:200]
    if not query:
        raise ReportError("Search for something first", status=400)

    docs = {d["reel_id"]: d for d in load_deep_search_documents(user_id) if d.get("reel_id")}
    include_set = {rid for rid in (include or []) if rid in docs}
    exclude_set = {rid for rid in (exclude or []) if rid in docs} - include_set

    results = search_user_documents(user_id, query, limit=MAX_CANDIDATES + len(exclude_set)).get("results") or []
    candidate_ids: list[str] = []
    for result in results:
        rid = result.get("reel_id")
        if rid in docs and rid not in exclude_set and rid not in candidate_ids:
            candidate_ids.append(rid)
    candidate_ids = candidate_ids[:MAX_CANDIDATES]
    for rid in include_set:
        if rid not in candidate_ids:
            candidate_ids.append(rid)
    excluded = [rid for rid in (exclude or []) if rid in exclude_set]

    if not candidate_ids:
        return {"status": "empty", "query": query, "title": query, "summary": "", "gaps": "",
                "sections": [], "used": [], "skipped": [], "cached": False, "usage": {}}

    key = _cache_key(user_id, query, candidate_ids, include_set)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT report_json FROM search_reports WHERE cache_key = ? LIMIT 1", (key,)
        ).fetchone()
    if row:
        report = json.loads(row["report_json"])
        return _payload(report, candidate_ids, excluded, docs, query, cached=True, usage={})

    if _generations_today(user_id) >= DAILY_GENERATIONS:
        raise ReportError(f"You've made {DAILY_GENERATIONS} reports today. More tomorrow.", status=429)

    labels = [f"R{i + 1}" for i in range(len(candidate_ids))]
    label_to_id = dict(zip(labels, candidate_ids))
    blocks = [_reel_block(label, docs[rid], rid in include_set) for label, rid in label_to_id.items()]
    try:
        raw, usage = _call_model(_prompt(query, blocks))
    except Exception as exc:
        raise ReportError("Couldn't write the report right now. Try again in a bit.") from exc

    report = _clean_report(raw, label_to_id, include_set)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO search_reports
                (user_id, query, cache_key, reel_ids_json, report_json, model,
                 prompt_tokens, completion_tokens, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                report_json = excluded.report_json,
                prompt_tokens = excluded.prompt_tokens,
                completion_tokens = excluded.completion_tokens,
                created_at = excluded.created_at
            """,
            (user_id, query, key, json.dumps(candidate_ids), json.dumps(report), REPORT_MODEL,
             usage["prompt_tokens"], usage["completion_tokens"], _now()),
        )
    return _payload(report, candidate_ids, excluded, docs, query, cached=False, usage=usage)
