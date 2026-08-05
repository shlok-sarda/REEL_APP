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


def _recipe_row(conn, user_id: str, reel_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT r.id AS reel_id, r.url,
               COALESCE(ri.item_name,'') item_name,
               COALESCE(ri.primary_category,'') primary_category,
               COALESCE(ri.secondary_category,'') specific_category,
               dsd.document_json
        FROM reels r
        LEFT JOIN reel_items ri ON ri.reel_id = r.id
        LEFT JOIN deep_search_documents dsd ON dsd.reel_id = r.id
        WHERE r.user_id = ? AND r.id = ?
        GROUP BY r.id
        """,
        (user_id, reel_id),
    ).fetchone()
    return dict(row) if row else None


def reel_recipe_status(user_id: str, reel_id: str) -> dict:
    """Per-reel recipe state, for the reel action sheet.
    status: 'recipe' (cached card) | 'candidate' (food reel with a transcript,
    extract on demand) | 'none' (not recipe material / confirmed not-a-recipe)."""
    with get_connection() as conn:
        cached = conn.execute(
            "SELECT is_recipe, recipe_json, shopping_json FROM reel_recipes WHERE user_id=? AND reel_id=?",
            (user_id, reel_id),
        ).fetchone()
        if cached:
            if cached["is_recipe"]:
                try:
                    card = json.loads(cached["recipe_json"])
                except Exception:
                    return {"status": "none"}
                try:
                    card["shopping"] = json.loads(cached["shopping_json"] or "[]")
                except Exception:
                    card["shopping"] = []
                return {"status": "recipe", "card": card, **QCOMMERCE_GEO}
            return {"status": "none"}
        row = _recipe_row(conn, user_id, reel_id)
    if not row:
        return {"status": "none"}
    cat = (row["primary_category"] + " " + row["specific_category"]).lower()
    if ("recipe" in cat or "food" in cat) and len(_transcript_of(row)) >= 120:
        return {"status": "candidate"}
    return {"status": "none"}


def extract_reel_recipe(user_id: str, reel_id: str) -> dict:
    """On-demand extraction for one reel (tapping 'Get recipe' in the sheet).
    Cached both ways, so each reel costs at most one call ever."""
    state = reel_recipe_status(user_id, reel_id)
    if state["status"] != "candidate":
        return state
    with get_connection() as conn:
        row = _recipe_row(conn, user_id, reel_id)
        if not row:
            return {"status": "none"}
        try:
            card = _extract_recipe_card(row, _transcript_of(row))
        except Exception:
            return {"status": "candidate", "error": "extraction_failed"}
        # Shopping data is allowlist-only while it bakes; everyone else keeps
        # today's card (and today's per-reel cost) exactly as it was.
        shopping = (
            _extract_shopping_rows(card, _shopping_text(row))
            if card and recipes_enabled(user_id)
            else []
        )
        conn.execute(
            "INSERT OR REPLACE INTO reel_recipes "
            "(user_id, reel_id, is_recipe, recipe_json, shopping_json, created_at) VALUES (?,?,?,?,?,?)",
            (user_id, reel_id, 1 if card else 0,
             json.dumps(card, ensure_ascii=False) if card else "",
             json.dumps(shopping, ensure_ascii=False), _now()),
        )
    if card:
        return {"status": "recipe", "card": {**card, "shopping": shopping}, **QCOMMERCE_GEO}
    return {"status": "none"}


def build_recipes(user_id: str, allow_extraction: bool = True) -> dict:
    """Extract recipe cards for food reels with transcripts; fully cached, both
    positive and negative outcomes, so nothing is ever paid for twice.
    allow_extraction=False serves cached rows only (shared demo-link sessions
    must not spend OpenAI credit)."""
    with get_connection() as conn:
        cached = {r["reel_id"]: r for r in conn.execute(
            "SELECT reel_id, is_recipe, recipe_json FROM reel_recipes WHERE user_id=?",
            (user_id,))}
        new_calls = 0 if allow_extraction else MAX_NEW_RECIPES_PER_CALL
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
            SELECT rr.reel_id, rr.recipe_json, rr.shopping_json, re.url,
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
            try:
                shopping = json.loads(r["shopping_json"] or "[]")
            except Exception:
                shopping = []
            recipes.append({**card, "reel_id": r["reel_id"], "url": r["url"],
                            "category": r["category"], "shopping": shopping})
        # backfill shopping for cached cards that predate the feature
        new_shopping = 0 if allow_extraction else MAX_NEW_SHOPPING_PER_CALL
        for rec in recipes:
            if rec["shopping"] or new_shopping >= MAX_NEW_SHOPPING_PER_CALL:
                continue
            row = _recipe_row(conn, user_id, rec["reel_id"])
            text = _shopping_text(row) if row else ""
            shopping = _extract_shopping_rows(rec, text)
            if shopping:
                rec["shopping"] = shopping
                conn.execute(
                    "UPDATE reel_recipes SET shopping_json=? WHERE user_id=? AND reel_id=?",
                    (json.dumps(shopping, ensure_ascii=False), user_id, rec["reel_id"]),
                )
                new_shopping += 1
    # recipes with exact product links surface first
    recipes.sort(key=lambda r: -sum(1 for s in r["shopping"] if s.get("exact")))
    return {"recipes": recipes, **QCOMMERCE_GEO}


# ---------------------------------------------------------------------------
# Ingredient shopping: per-ingredient quick-commerce buy links.
#
# Search URL formats verified live in a browser 2026-07-25 (Blinkit renders
# results behind a dismissible location modal; Instamart works logged-out;
# Zepto web search wants login but app links hand off to the installed app;
# Flipkart Minutes = marketplace=HYPERLOCAL, mobile-web/app only). Exact
# product links (blinkit /prn/.../prid/, zepto /pn/.../pvid/, bigbasket /pd/)
# are resolved OFFLINE by the lab pipeline (deep_search_lab/ingredient_links.py
# resolve stage) and land here via shopping_json — the app itself never
# scrapes or calls out to the platforms.
# ---------------------------------------------------------------------------

MAX_NEW_SHOPPING_PER_CALL = 12


def recipes_enabled(user_id: str) -> bool:
    """Who sees the Recipes hub + ingredient buy links.

    Admin accounts (the founder is always one, see settings.admin_emails)
    plus anything in the RECIPES_ACCOUNTS env var, by email or user id —
    the same solo-bake rollout dial Collections used.
    """
    from app.config import settings

    if not user_id:
        return False
    allowlist = settings.recipes_accounts
    if user_id.strip().lower() in allowlist:
        return True
    with get_connection() as conn:
        row = conn.execute(
            "SELECT lower(email) AS email FROM users WHERE id = ? LIMIT 1", (user_id,)
        ).fetchone()
    email = (row["email"] or "") if row else ""
    return bool(email) and (email in settings.admin_emails or email in allowlist)

QCOMMERCE_GEO = {
    "apps": {
        "blinkit": {"label": "Blinkit", "color": "#f8cb46"},
        "zepto": {"label": "Zepto", "color": "#950ed1"},
        "instamart": {"label": "Instamart", "color": "#fc8019"},
        "flipkart": {"label": "Fk Minutes", "color": "#2874f0"},
        "bigbasket": {"label": "bbNow", "color": "#84c225"},
        "jiomart": {"label": "JioMart", "color": "#008ecc"},
        "amazon": {"label": "Amazon", "color": "#febd69"},
    },
    "default_apps": ["blinkit", "instamart", "flipkart", "jiomart", "amazon"],
    # City coverage as of mid-2026 (researched): Blinkit ~330 cities,
    # Instamart 129, Fk Minutes 130+, Zepto metro-dense, bbNow ~35.
    "cities": {
        "Mumbai": ["blinkit", "zepto", "instamart", "flipkart", "bigbasket", "jiomart", "amazon"],
        "Delhi NCR": ["blinkit", "zepto", "instamart", "flipkart", "bigbasket", "jiomart", "amazon"],
        "Bengaluru": ["blinkit", "zepto", "instamart", "flipkart", "bigbasket", "jiomart", "amazon"],
        "Hyderabad": ["blinkit", "zepto", "instamart", "flipkart", "bigbasket", "jiomart", "amazon"],
        "Chennai": ["blinkit", "zepto", "instamart", "flipkart", "bigbasket", "jiomart"],
        "Kolkata": ["blinkit", "zepto", "instamart", "flipkart", "bigbasket", "jiomart"],
        "Pune": ["blinkit", "zepto", "instamart", "flipkart", "bigbasket", "jiomart", "amazon"],
        "Ahmedabad": ["blinkit", "zepto", "instamart", "flipkart", "bigbasket", "jiomart"],
        "Jaipur": ["blinkit", "zepto", "instamart", "flipkart", "jiomart"],
        "Lucknow": ["blinkit", "zepto", "instamart", "flipkart", "bigbasket", "jiomart"],
        "Chandigarh": ["blinkit", "zepto", "instamart", "flipkart", "bigbasket", "jiomart"],
        "Indore": ["blinkit", "zepto", "instamart", "flipkart", "bigbasket", "jiomart"],
        "Varanasi": ["blinkit", "zepto", "instamart", "flipkart", "bigbasket", "jiomart"],
        "Patna": ["blinkit", "instamart", "flipkart", "bigbasket", "jiomart"],
        "Kochi": ["blinkit", "zepto", "instamart", "flipkart", "bigbasket", "jiomart", "amazon"],
        "Goa": ["blinkit", "instamart", "jiomart"],
        "Other / smaller city": ["blinkit", "instamart", "flipkart", "jiomart", "amazon"],
    },
}

SHOPPING_PROMPT_RULES = (
    "For EVERY ingredient in the list, return JSON: "
    '{"ingredients": [{"display": "<ingredient exactly as given>", '
    '"query": "<short generic grocery-app search query, no quantities and NO '
    'brand names>", "brand": "<brand ONLY if the reel text clearly names one '
    'for THIS ingredient, else empty>", "branded_query": "<brand + product if '
    'brand set, else empty>", "pantry": <true for basic staples like salt, '
    "water, sugar, plain cooking oil>}]}\n"
    "Rules: one output per input ingredient, same order, none skipped. "
    "query must be something you can buy on Blinkit/Zepto. Do NOT invent "
    "brands; fix obvious speech-to-text mangling of brand names when "
    "confident. Return ONLY the JSON object."
)


def _shopping_links_for(query: str) -> dict:
    q = urllib.parse.quote_plus(query.strip())
    qs = urllib.parse.quote(query.strip())
    return {
        "blinkit": "https://blinkit.com/s/?q=" + q,
        "zepto": "https://www.zeptonow.com/search?query=" + q,
        "instamart": "https://www.swiggy.com/instamart/search?custom_back=true&query=" + qs,
        "flipkart": "https://www.flipkart.com/search?marketplace=HYPERLOCAL&q=" + q,
        "bigbasket": "https://www.bigbasket.com/ps/?q=" + q,
        "jiomart": "https://www.jiomart.com/search?q=" + q,
        "amazon": "https://www.amazon.in/s?k=" + q,
    }


def _shopping_text(row: dict) -> str:
    """Transcript + caption — captions often carry the cleanest recipe copy."""
    try:
        doc = json.loads(row.get("document_json") or "{}")
    except Exception:
        return ""
    transcript = _norm(doc.get("transcript"))
    caption = _norm(doc.get("caption"))
    if caption:
        return (transcript + "\n\nCAPTION:\n" + caption).strip()
    return transcript


def _extract_shopping_rows(card: dict, text: str) -> list[dict]:
    """One gpt-4.1-mini call: ingredient strings -> shoppable queries + brands
    -> per-app links. Returns [] on any failure so callers can retry later."""
    from api_config import get_openai_client

    ingredients = card.get("ingredients") or []
    if not ingredients:
        return []
    prompt = (
        f"Recipe: {card.get('title', '')}\n"
        "Ingredient list:\n" + "\n".join(f"- {i}" for i in ingredients) + "\n\n"
        "Reel text (may be garbled Hindi/Hinglish speech-to-text):\n"
        + (text or "(no text)")[:4000] + "\n\n" + SHOPPING_PROMPT_RULES
    )
    try:
        client = get_openai_client()
        resp = client.chat.completions.create(
            model=RECIPE_MODEL,
            messages=[
                {"role": "system", "content": "You turn recipe ingredients into clean grocery-app search queries."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
    except Exception:
        return []
    rows = []
    for ing in data.get("ingredients") or []:
        display = _norm(ing.get("display"))
        query = _norm(ing.get("query")) or display
        brand = _norm(ing.get("brand"))
        branded_query = _norm(ing.get("branded_query"))
        rows.append({
            "display": display,
            "query": query,
            "brand": brand,
            "branded_query": branded_query,
            "pantry": bool(ing.get("pantry")),
            "links": _shopping_links_for(branded_query or query),
            "exact": {},
        })
    return rows


def recipe_shopping(user_id: str, reel_id: str) -> list[dict]:
    """Cached shopping rows for one recipe, extracting on first request."""
    with get_connection() as conn:
        cached = conn.execute(
            "SELECT recipe_json, shopping_json FROM reel_recipes "
            "WHERE user_id=? AND reel_id=? AND is_recipe=1",
            (user_id, reel_id),
        ).fetchone()
        if not cached:
            return []
        try:
            shopping = json.loads(cached["shopping_json"] or "[]")
        except Exception:
            shopping = []
        if shopping:
            return shopping
        try:
            card = json.loads(cached["recipe_json"])
        except Exception:
            return []
        row = _recipe_row(conn, user_id, reel_id)
        shopping = _extract_shopping_rows(card, _shopping_text(row) if row else "")
        if shopping:
            conn.execute(
                "UPDATE reel_recipes SET shopping_json=? WHERE user_id=? AND reel_id=?",
                (json.dumps(shopping, ensure_ascii=False), user_id, reel_id),
            )
    return shopping
