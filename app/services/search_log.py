"""Search ground truth: what people typed, what came back, what they opened.

Queries are private to the user who typed them. They stay in the app DB and
are only read back through the admin endpoints.

Every public function here swallows its own errors. A failed log write must
never turn a working search into an error.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.database import get_connection

# Search runs as the user types, so one intent arrives as "c", "ca", "cafe".
# A request that extends (or backspaces) the user's previous one inside this
# window updates that row instead of adding a new one.
TYPING_WINDOW_SECONDS = 20
# USD per million tokens (input, cached input, output), OpenAI list prices as
# used in the July-September cost measurements. Models missing here are
# reported with tokens only, never a guessed cost.
PRICE_USD_PER_M = {
    "gpt-4.1": (2.00, 0.50, 8.00),
    "gpt-4.1-mini": (0.40, 0.10, 1.60),
    "gpt-4.1-nano": (0.10, 0.025, 0.40),
    "text-embedding-3-small": (0.02, 0.02, 0.0),
}
USD_INR = 88.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _result_ids(payload: dict[str, Any]) -> list[str]:
    results = payload.get("results")
    if not isinstance(results, list):
        return []
    return [str(r.get("reel_id")) for r in results if isinstance(r, dict) and r.get("reel_id")]


def log_search(user_id: str, query: str, payload: dict[str, Any], latency_ms: int) -> int | None:
    """Record one search. Returns the row id the UI attaches to clicks."""
    try:
        ids = _result_ids(payload)
        now = _now()
        stamp = now.isoformat()
        cutoff = (now - timedelta(seconds=TYPING_WINDOW_SECONDS)).isoformat()
        backend = str(payload.get("backend") or "")
        with get_connection() as connection:
            last = connection.execute(
                "SELECT id, query FROM search_queries WHERE user_id = ? AND updated_at >= ? "
                "ORDER BY id DESC LIMIT 1",
                (user_id, cutoff),
            ).fetchone()
            if last:
                old, new = last["query"].lower(), query.lower()
                if new.startswith(old) or old.startswith(new):
                    connection.execute(
                        "UPDATE search_queries SET query = ?, backend = ?, result_count = ?, "
                        "result_reel_ids = ?, latency_ms = ?, keystrokes = keystrokes + 1, "
                        "updated_at = ? WHERE id = ?",
                        (query, backend, len(ids), json.dumps(ids), latency_ms, stamp, last["id"]),
                    )
                    return int(last["id"])
            cursor = connection.execute(
                "INSERT INTO search_queries (user_id, query, backend, result_count, "
                "result_reel_ids, latency_ms, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, query, backend, len(ids), json.dumps(ids), latency_ms, stamp, stamp),
            )
            return int(cursor.lastrowid)
    except Exception:
        return None


def log_click(user_id: str, query_id: Any, query: str, reel_id: str, shown_position: Any) -> bool:
    """Record a result the user opened. server_position is where the server
    ranked it (-1 when only the on-device match found it)."""
    try:
        reel_id = str(reel_id or "").strip()
        if not reel_id:
            return False
        try:
            qid = int(query_id)
        except (TypeError, ValueError):
            qid = None
        try:
            shown = int(shown_position)
        except (TypeError, ValueError):
            shown = -1
        server_position = -1
        with get_connection() as connection:
            if qid is not None:
                row = connection.execute(
                    "SELECT result_reel_ids FROM search_queries WHERE id = ? AND user_id = ?",
                    (qid, user_id),
                ).fetchone()
                if row is None:
                    qid = None
                else:
                    ids = json.loads(row["result_reel_ids"] or "[]")
                    if reel_id in ids:
                        server_position = ids.index(reel_id)
            connection.execute(
                "INSERT INTO search_clicks (query_id, user_id, query, reel_id, shown_position, "
                "server_position, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (qid, user_id, str(query or "").strip()[:500], reel_id, shown, server_position, _now().isoformat()),
            )
        return True
    except Exception:
        return False


def recent_searches(days: int = 30, limit: int = 500) -> dict[str, Any]:
    cutoff = (_now() - timedelta(days=days)).isoformat()
    with get_connection() as connection:
        queries = [dict(r) for r in connection.execute(
            "SELECT id, user_id, query, backend, result_count, result_reel_ids, latency_ms, "
            "keystrokes, created_at FROM search_queries WHERE updated_at >= ? ORDER BY id DESC LIMIT ?",
            (cutoff, limit),
        )]
        clicks = [dict(r) for r in connection.execute(
            "SELECT query_id, user_id, query, reel_id, shown_position, server_position, created_at "
            "FROM search_clicks WHERE created_at >= ? ORDER BY id DESC LIMIT ?",
            (cutoff, limit),
        )]
    by_query: dict[int, list[dict]] = {}
    for click in clicks:
        if click["query_id"] is not None:
            by_query.setdefault(click["query_id"], []).append(click)
    for row in queries:
        row["result_reel_ids"] = json.loads(row["result_reel_ids"] or "[]")
        row["clicks"] = by_query.get(row["id"], [])
    return {
        "days": days,
        "query_count": len(queries),
        "zero_result_count": sum(1 for q in queries if not q["result_count"]),
        "clicked_query_count": sum(1 for q in queries if q["clicks"]),
        "click_count": len(clicks),
        "clicks_server_missed": sum(1 for c in clicks if c["server_position"] < 0),
        "queries": queries,
        "unattached_clicks": [c for c in clicks if c["query_id"] is None],
    }


def _cost_inr(model: str, prompt: int, cached: int, completion: int) -> float | None:
    price = PRICE_USD_PER_M.get(model)
    if not price:
        return None
    usd = ((prompt - cached) * price[0] + cached * price[1] + completion * price[2]) / 1_000_000
    return round(usd * USD_INR, 4)


def llm_usage_summary(days: int = 7) -> dict[str, Any]:
    """Spend by call site, plus the per-reel average for runs tagged to a reel."""
    cutoff = (_now() - timedelta(days=days)).isoformat()
    with get_connection() as connection:
        rows = [dict(r) for r in connection.execute(
            "SELECT script, caller, kind, model, COUNT(*) AS calls, SUM(prompt_tokens) AS prompt_tokens, "
            "SUM(completion_tokens) AS completion_tokens, SUM(cached_tokens) AS cached_tokens, "
            "SUM(audio_seconds) AS audio_seconds, COUNT(DISTINCT NULLIF(reel, '')) AS reels "
            "FROM llm_usage WHERE created_at >= ? GROUP BY script, caller, kind, model "
            "ORDER BY SUM(prompt_tokens) + SUM(completion_tokens) DESC",
            (cutoff,),
        )]
        reels = connection.execute(
            "SELECT COUNT(DISTINCT reel) FROM llm_usage WHERE created_at >= ? AND reel != ''", (cutoff,)
        ).fetchone()[0]
    total, unpriced = 0.0, []
    for row in rows:
        row["cost_inr"] = _cost_inr(row["model"], row["prompt_tokens"], row["cached_tokens"], row["completion_tokens"])
        if row["cost_inr"] is None:
            unpriced.append(row["model"])
        else:
            total += row["cost_inr"]
    return {
        "days": days,
        "usd_inr": USD_INR,
        "priced_total_inr": round(total, 2),
        "unpriced_models": sorted(set(unpriced)),
        "reels_processed": reels,
        "priced_inr_per_reel_all_in": round(total / reels, 4) if reels else None,
        "note": "Download (Apify) is not an OpenAI call and is not counted. Unpriced models show tokens only.",
        "by_call_site": rows,
    }
