"""Discover features: the reel map (places) and recipe cards.

Ported from the lab prototypes (deep_search_lab/location_extract.py and
recipe_extract.py) onto the live database.

Map: mines place names from fields extraction already produced (item_name
parentheticals, "X in <Place>" category patterns, a small gazetteer tuned to
Shlok's data), geocodes via OpenStreetMap Nominatim (free, 1 req/sec, cached
forever in the geocode_cache table), and stores pins in reel_locations.

Recipes: food/recipe-category reels with a usable transcript go through one
gpt-4.1-mini call that either returns a structured recipe card or flags the
reel as not-a-cook-along (restaurant recs stay on the map instead). Both
outcomes are cached in reel_recipes so a reel is never paid for twice.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

from app.db.database import get_connection

RECIPE_MODEL = "gpt-4.1-mini"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ClipNest/1.0 (personal reel map)"
MAX_NEW_GEOCODES_PER_CALL = 25   # first call warms slowly; later calls are instant
MAX_NEW_RECIPES_PER_CALL = 40

ALIASES = {
    "banaras": "Varanasi", "benares": "Varanasi", "kashi": "Varanasi",
    "bombay": "Mumbai", "blr": "Bengaluru", "bangalore": "Bengaluru",
}

GAZETTEER = {
    "varanasi", "nadesar", "goa", "mumbai", "delhi", "new delhi", "bengaluru",
    "bangalore", "pune", "jaipur", "udaipur", "kolkata", "chennai", "hyderabad",
    "candolim", "candolim beach", "anjuna", "baga", "calangute", "panjim",
    "rishikesh", "manali", "meghalaya", "shillong", "kerala", "munnar",
    "leh", "ladakh", "kasol", "spiti", "gokarna", "hampi", "pushkar",
    "nepal", "pokhara", "kathmandu",
    "bali", "dubai", "bangkok", "singapore", "paris", "london", "tokyo",
    "new york", "thailand", "vietnam", "sri lanka", "noida", "gurgaon",
    "lucknow", "agra", "amritsar", "chandigarh", "indore", "surat",
}
MULTIWORD = sorted([g for g in GAZETTEER if " " in g], key=len, reverse=True)

IN_PATTERN = re.compile(r"\b(?:in|at|near|from)\s+([A-Z][\w'&-]+(?:\s+[A-Z][\w'&-]+){0,2})")
PAREN_PATTERN = re.compile(r"\(([^)]+)\)")
NOT_PLACES = {
    "joke", "movie", "mr", "mrs", "ms", "dr", "the", "a", "an", "part",
    "episode", "recipe", "review", "tutorial", "guide", "vlog", "day",
}
PLACE_CLASSES = {"place", "boundary", "tourism", "amenity", "leisure", "natural", "shop"}


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _norm(text) -> str:
    return " ".join(str(text or "").strip().split())


def _canonical(place: str) -> str:
    return ALIASES.get(place.lower().strip(), place.strip())


def _gazetteer_hit(field: str) -> str | None:
    low = field.lower()
    for g in MULTIWORD:
        if g in low:
            return g.title()
    for token in re.findall(r"[a-z]+", low):
        if token in GAZETTEER:
            return token.title()
    return None


def _looks_like_place(cand: str) -> bool:
    low = cand.lower().strip()
    if not low or low in NOT_PLACES or len(low) <= 2:
        return False
    if re.fullmatch(r"[\d\s,.-]+", low):
        return False
    return True


def _extract_place(name: str, spec: str, transcript: str) -> tuple[str, bool] | None:
    """(canonical_place, trusted) or None. trusted = gazetteer match; loose
    grabs must resolve to a real place-class in geocoding."""
    for field in (spec, name):
        hit = _gazetteer_hit(field)
        if hit:
            return _canonical(hit), True
    for m in PAREN_PATTERN.findall(name):
        parts = [p.strip() for p in m.split(",") if p.strip()]
        if parts and _looks_like_place(parts[-1]):
            return _canonical(parts[-1]), False
    for field in (spec, name):
        m = IN_PATTERN.search(field)
        if m and _looks_like_place(m.group(1).strip()):
            return _canonical(m.group(1).strip()), False
    hit = _gazetteer_hit(transcript)
    if hit:
        return _canonical(hit), True
    return None


def _geocode(conn, place: str, trusted: bool) -> dict | None:
    cached = conn.execute(
        "SELECT result_json FROM geocode_cache WHERE place=?", (place,)
    ).fetchone()
    if cached:
        return json.loads(cached["result_json"]) if cached["result_json"] else None
    params = urllib.parse.urlencode({"q": place, "format": "json", "limit": 1})
    req = urllib.request.Request(f"{NOMINATIM}?{params}", headers={"User-Agent": USER_AGENT})
    result = None
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            rows = json.loads(resp.read().decode())
        if rows:
            r = rows[0]
            if trusted or r.get("class") in PLACE_CLASSES:
                result = {"lat": float(r["lat"]), "lng": float(r["lon"]),
                          "display": r.get("display_name", place)}
    except Exception:
        return None  # network hiccup: don't cache, retry next call
    conn.execute(
        "INSERT OR REPLACE INTO geocode_cache (place, result_json, created_at) VALUES (?,?,?)",
        (place, json.dumps(result) if result else "", _now()),
    )
    time.sleep(1.1)  # Nominatim fair-use: ~1 req/sec
    return result


def _discover_rows(conn, user_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """
        SELECT r.id AS reel_id, r.url,
               COALESCE(ri.item_name,'') item_name,
               COALESCE(ri.primary_category,'') primary_category,
               COALESCE(ri.secondary_category,'') specific_category,
               dsd.document_json
        FROM reels r
        LEFT JOIN reel_items ri ON ri.reel_id = r.id
        LEFT JOIN deep_search_documents dsd ON dsd.reel_id = r.id
        WHERE r.user_id = ?
        GROUP BY r.id
        """,
        (user_id,),
    )]


def _transcript_of(row: dict) -> str:
    try:
        doc = json.loads(row.get("document_json") or "{}")
    except Exception:
        return ""
    return _norm(doc.get("transcript"))


def build_map_pins(user_id: str) -> dict:
    """Extract + geocode place pins for every reel that doesn't have one yet.
    Returns all pins plus how many places are still waiting on geocoding."""
    with get_connection() as conn:
        have = {r["reel_id"] for r in conn.execute(
            "SELECT reel_id FROM reel_locations WHERE user_id=?", (user_id,))}
        new_geocodes = 0
        pending = 0
        for row in _discover_rows(conn, user_id):
            if row["reel_id"] in have:
                continue
            hit = _extract_place(_norm(row["item_name"]), _norm(row["specific_category"]),
                                 _transcript_of(row))
            if not hit:
                continue
            place, trusted = hit
            cached = conn.execute(
                "SELECT 1 FROM geocode_cache WHERE place=?", (place,)).fetchone()
            if not cached and new_geocodes >= MAX_NEW_GEOCODES_PER_CALL:
                pending += 1
                continue
            if not cached:
                new_geocodes += 1
            geo = _geocode(conn, place, trusted)
            if not geo:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO reel_locations "
                "(user_id, reel_id, place, lat, lng, display, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (user_id, row["reel_id"], place, geo["lat"], geo["lng"],
                 geo.get("display", place), _now()),
            )
        pins = [dict(r) for r in conn.execute(
            """
            SELECT rl.reel_id, rl.place, rl.lat, rl.lng,
                   COALESCE(ri.item_name,'') item_name,
                   COALESCE(ri.primary_category,'') category,
                   r.url
            FROM reel_locations rl
            JOIN reels r ON r.id = rl.reel_id
            LEFT JOIN reel_items ri ON ri.reel_id = rl.reel_id
            WHERE rl.user_id=?
            GROUP BY rl.reel_id
            """,
            (user_id,),
        )]
    return {"pins": pins, "pending_places": pending}


def _extract_recipe_card(row: dict, transcript: str) -> dict | None:
    """One gpt-4.1-mini call; returns the card dict or None for not-a-recipe."""
    from api_config import get_openai_client

    prompt = (
        "You are given the transcript (and title) of a saved Instagram food reel.\n\n"
        "Decide if this is an actual COOK-ALONG RECIPE (someone making a dish you "
        "could follow). Restaurant recommendations, food reviews, 'best spot in "
        "<city>' reels, and vlogs are NOT recipes.\n\n"
        'If it is NOT a cook-along recipe, return exactly: {"is_recipe": false}\n\n'
        "If it IS a recipe, return JSON:\n"
        '{"is_recipe": true, "title": "<short dish name>", "servings": "<or empty>", '
        '"total_time": "<or empty>", "ingredients": ["<with qty if stated>"], '
        '"steps": ["<imperative step>"]}\n\n'
        "Rules: steps in cooking order, concise, derived only from the transcript. "
        "Do not invent ingredients or quantities. 3-10 steps typical. "
        "Return ONLY the JSON object.\n\n"
        f"TITLE: {row['item_name']}\nTRANSCRIPT:\n{transcript[:4000]}"
    )
    client = get_openai_client()
    resp = client.chat.completions.create(
        model=RECIPE_MODEL,
        messages=[
            {"role": "system", "content": "You convert short cooking-video transcripts into clean, structured recipe cards."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    if not data.get("is_recipe"):
        return None
    return {
        "title": data.get("title") or row["item_name"],
        "servings": str(data.get("servings", "")),
        "total_time": str(data.get("total_time", "")),
        "ingredients": [str(x) for x in (data.get("ingredients") or [])],
        "steps": [str(x) for x in (data.get("steps") or [])],
    }


def build_recipes(user_id: str) -> dict:
    """Extract recipe cards for food reels with transcripts; fully cached, both
    positive and negative outcomes, so nothing is ever paid for twice."""
    with get_connection() as conn:
        cached = {r["reel_id"]: r for r in conn.execute(
            "SELECT reel_id, is_recipe, recipe_json FROM reel_recipes WHERE user_id=?",
            (user_id,))}
        new_calls = 0
        for row in _discover_rows(conn, user_id):
            if row["reel_id"] in cached or new_calls >= MAX_NEW_RECIPES_PER_CALL:
                continue
            cat = (row["primary_category"] + " " + row["specific_category"]).lower()
            transcript = _transcript_of(row)
            if not (("recipe" in cat or "food" in cat) and len(transcript) >= 120):
                continue
            try:
                card = _extract_recipe_card(row, transcript)
            except Exception:
                continue  # key/quota hiccup: retry on a later call
            new_calls += 1
            conn.execute(
                "INSERT OR REPLACE INTO reel_recipes "
                "(user_id, reel_id, is_recipe, recipe_json, created_at) VALUES (?,?,?,?,?)",
                (user_id, row["reel_id"], 1 if card else 0,
                 json.dumps(card, ensure_ascii=False) if card else "", _now()),
            )
        recipes = []
        for r in conn.execute(
            """
            SELECT rr.reel_id, rr.recipe_json, re.url,
                   COALESCE(ri.primary_category,'') category
            FROM reel_recipes rr
            JOIN reels re ON re.id = rr.reel_id
            LEFT JOIN reel_items ri ON ri.reel_id = rr.reel_id
            WHERE rr.user_id=? AND rr.is_recipe=1
            GROUP BY rr.reel_id
            ORDER BY rr.created_at DESC
            """,
            (user_id,),
        ):
            try:
                card = json.loads(r["recipe_json"])
            except Exception:
                continue
            recipes.append({**card, "reel_id": r["reel_id"], "url": r["url"],
                            "category": r["category"]})
    return {"recipes": recipes}
