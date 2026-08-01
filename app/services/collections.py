"""Shelf Router — the Collections engine.

Sorts saved reels onto a small set of BROAD shelves, one shelf per recurring
interest, and leaves everything else off the shelves entirely.

Why it looks like this (all of it measured on the real library, not guessed):

* It routes on the reel's MAIN SUBJECT and nothing else. The previous engine
  clustered `reel_item_features.canonical_subdomains`, produced by a keyword
  heuristic, which tagged a reel whose subject is "young woman with long curled
  hair modeling a beige pullover" as ["men's clothing brands"] and filed it
  under menswear. Incidental clothes, props and brand mentions must never
  decide a shelf, so this module reads none of those fields.
* No embeddings. Cosine similarity against fixed shelf definitions puts that
  same reel's argmax on "Fashion & Shopping" (0.384) — the geometry votes FOR
  the bug, so there is no threshold that rescues it.
* The vocabulary is a fixed constant and the model may only select from it or
  answer "none". "Chest Workout" is unrepresentable by construction, which is
  how shelves stay broad without tuning.
* Three votes per reel, majority wins. temperature=0 is not a determinism
  guarantee: a single call flipped 3/25 reels across identical runs. Votes plus
  write-once persistence are what make the shelves stable.
* Every verdict is persisted forever against a hash of the card that produced
  it, so a rebuild costs nothing unless a reel's extraction actually changed.

Coverage is explicitly not a goal. Most reels belong on no shelf and that is
the correct outcome — they stay reachable through search and Recently saved.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter

from app.db.database import get_connection


PROMPT_VERSION = "shelves_v1"
ROUTE_MODEL = "gpt-4.1-mini"
ROUTE_SEEDS = (7, 8, 9)
ROUTE_TEMPERATURE = 0
ROUTE_MAX_TOKENS = 25

# A reel three passes cannot agree on is not squarely about anything, which is
# the same thing as belonging on no shelf.
ROUTE_MIN_VOTES = 2

# Three, not five. The unit here is a REEL, so a single caption listicle can no
# longer manufacture a shelf out of its own twelve items — that was what forced
# the old floor up, and the old floor is what killed "Restaurants in Goa" at
# four members with perfect purity.
MIN_SHELF_MEMBERS = 3
MAX_SHELVES = 12

# reel_7's transcript is 43 chars of small talk; the median real transcript in
# the library is 621. The boundary sits an order of magnitude from both.
TRANSCRIPT_INCIDENTAL_CHARS = 80
CARD_BRANDS_MAX = 120
CARD_PRODUCTS_MAX = 120
CARD_SUMMARY_MAX = 180

_FAIL_MARKERS = ("processing failed", "could not be processed", "failed reels")


CORE_VOCAB: dict[str, str] = {
    "Food & Restaurants": "a dish, a meal, a cafe or a restaurant, judged by its food",
    "Recipes & Cooking": "how to cook something; the ingredients and the method are the point",
    "Travel & Places": "a destination, a stay, an itinerary or a trip; the place is the point",
    "Gym & Fitness": "training, exercise form, workouts, sport technique",
    "Gadgets & Tech": "a physical device or gadget being shown, reviewed or repaired",
    "Apps & AI Tools": "software, an app, a website or an AI tool being demonstrated",
    "Fashion & Shopping": (
        "clothes, jewellery, footwear or fragrance being SOLD or recommended, with a brand, "
        "a product or a buy-link. NEVER a person who is simply wearing something"
    ),
    "Grooming & Personal Care": "hair, skin or grooming ROUTINES and products",
    "Movies & Shows": "a film or a series being discussed, recommended or clipped",
    "Money & Career": "jobs, business, study, funding, personal finance",
    "People & Performance": (
        "a person is the point: singing, dancing, modelling, getting ready, hanging out, "
        "a transition or an edit. Nothing is being sold or taught"
    ),
    "Home & Decor": "furniture, lighting, room styling and home objects",
    "Cars & Rides": "cars, bikes and vehicles",
    "Music": "songs, artists, instruments and music gear",
    "Books & Reading": "books and reading",
    "Pets & Animals": "animals",
    "Art & Design": "art, illustration and design work",
    "Hobbies & Collecting": "a hobby object or a collection: RC cars, models, toys, gear",
}


# Rule 1 is load-bearing and was added after measurement: without it, "young man
# lifting dumbbells in a gym" routed to People & Performance and the gym test
# failed outright. Rule 2 is the one that fixes the founder's reported bug — no
# field in the database draws the "wearing clothes" vs "selling clothes"
# distinction, and that distinction is the entire reason an LLM is here at all.
_ROUTE_RULES = """
Decide from the reel's MAIN SUBJECT only.

1. ACTIVITY BEATS APPEARANCE. If the subject is doing a recognisable activity, the shelf
is that activity: lifting weights or training is Gym & Fitness, cooking is Recipes &
Cooking, travelling or showing a place is Travel & Places, demonstrating an app is Apps &
AI Tools.
2. If the subject is a person simply being on camera - singing, dancing, modelling,
getting ready, lip-syncing, an outfit transition, an edit, hanging out - and 'brands:
none' + 'products: none' + 'spoken: none/incidental' confirm nobody is selling or teaching
anything, the shelf is People & Performance, or none. NEVER Fashion, Grooming or Gadgets
just because clothes, hair or objects are visible.
3. Ignore incidental details completely: a presenter's outfit, background props, a brand
mentioned in passing, where it happened to be filmed.
4. "none" is always allowed and is the right answer whenever no shelf is squarely about
this reel. Most reels belong on no shelf and that is correct. Never stretch a reel to fill
a shelf.
5. When a shelf does fit, pick the BROADEST one that fits. Never narrow it.
Reply JSON only: {"shelf":"<exact name from the list>"|"none"}
""".strip()


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS collection_routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        reel_id TEXT NOT NULL,
        card_hash TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        shelf_key TEXT NOT NULL DEFAULT '',
        votes_json TEXT NOT NULL DEFAULT '[]',
        model TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        UNIQUE(user_id, reel_id, card_hash, prompt_version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS collection_shelves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        shelf_key TEXT NOT NULL,
        list_title TEXT NOT NULL,
        parent_title TEXT NOT NULL DEFAULT '',
        member_count INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'published',
        rank INTEGER NOT NULL DEFAULT 0,
        built_at TEXT NOT NULL,
        UNIQUE(user_id, shelf_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS collection_memberships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        shelf_key TEXT NOT NULL,
        reel_id TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'router',
        created_at TEXT NOT NULL,
        UNIQUE(user_id, shelf_key, reel_id)
    )
    """,
]

_INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_collection_routes_user ON collection_routes(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_collection_routes_reel ON collection_routes(user_id, reel_id)",
    "CREATE INDEX IF NOT EXISTS idx_collection_memberships_user ON collection_memberships(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_collection_shelves_user ON collection_shelves(user_id, status)",
]

_schema_ready = False


def ensure_schema() -> None:
    """Create this engine's tables if they are missing.

    Deliberately self-contained rather than living in app/db/init_db.py: that
    file carries another session's uncommitted work, and committing it to ship
    three CREATE TABLEs is exactly how a partial commit took prod down on
    2026-07-15. Idempotent, so folding it back into SCHEMA_STATEMENTS later is
    a no-op.
    """
    global _schema_ready
    if _schema_ready:
        return
    with get_connection() as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        for statement in _INDEX_STATEMENTS:
            connection.execute(statement)
    _schema_ready = True


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _text(value) -> str:
    return " ".join(str(value or "").strip().split())


def _join(values) -> str:
    if not isinstance(values, list):
        return ""
    return ", ".join(_text(value) for value in values if _text(value))


def vocabulary_for(user_id: str) -> dict[str, str]:
    """The shelves that may exist. Fixed vocabulary, so shelves stay broad."""
    return dict(CORE_VOCAB)


def route_system_prompt(vocab: dict[str, str]) -> str:
    block = "\n".join(f"- {term}: {definition}" for term, definition in vocab.items())
    return (
        "You sort a person's saved Instagram reels onto BROAD shelves.\n\n"
        "These are the only shelves that exist:\n"
        f"{block}\n\n"
        f"{_ROUTE_RULES}"
    )


def _reel_rows(user_id: str) -> list[dict]:
    # One row per REEL. The GROUP BY is what stops a caption listicle ("20
    # restaurants in Bali") from contributing twelve separate cards and
    # single-handedly manufacturing a shelf.
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                reels.id AS reel_id,
                reels.url AS url,
                reels.received_at AS received_at,
                reels.local_video_path AS local_video_path,
                reels.thumbnail_path AS thumbnail_path,
                deep_search_documents.document_json AS document_json,
                MIN(reel_items.item_name) AS item_name,
                MIN(reel_items.summary) AS summary,
                json_extract(reel_processing_diagnostics.metadata_json, '$.main_subject_type') AS main_subject_type
            FROM reels
            JOIN deep_search_documents ON deep_search_documents.reel_id = reels.id
            LEFT JOIN reel_processing_diagnostics ON reel_processing_diagnostics.reel_id = reels.id
            LEFT JOIN reel_items ON reel_items.reel_id = reels.id
            WHERE reels.user_id = ? AND reels.status = 'completed'
            GROUP BY reels.id
            ORDER BY reels.id
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def build_card(row: dict) -> str | None:
    """Compress a reel into the only representation the router ever sees.

    Returns None when the reel carries no usable subject at all — it is then
    NOT ROUTABLE, no verdict is stored, and it appears on no shelf.
    """
    try:
        document = json.loads(row.get("document_json") or "{}")
    except Exception:
        document = {}

    item_name = _text(row.get("item_name"))
    summary = _text(row.get("summary"))
    # A reel that failed processing must never become a "Failed Reels" shelf,
    # which is what the previous engine rendered to the user.
    if any(marker in f"{item_name} {summary}".lower() for marker in _FAIL_MARKERS):
        item_name = ""
        summary = ""

    main_subject = _text(document.get("main_subject"))
    visual_theme = _text(document.get("visual_theme"))
    if not (main_subject or visual_theme or item_name or summary):
        return None

    transcript = str(document.get("transcript") or "")
    if not transcript.strip():
        spoken = "spoken: none"
    elif len(transcript) < TRANSCRIPT_INCIDENTAL_CHARS:
        spoken = "spoken: incidental only"
    else:
        spoken = f"spoken: explains/teaches ({len(transcript)} chars)"

    about = ""
    if visual_theme:
        about = f"about: {visual_theme}"
    elif summary:
        about = f"about: {summary[:CARD_SUMMARY_MAX]}"

    lines = [
        f"subject: {main_subject or item_name or '(unknown)'}",
        f"subject type: {_text(row.get('main_subject_type')) or 'unknown'}",
        about,
        # Brands and products are intent evidence only — the prompt uses
        # "none/none/none" to recognise a watch-only reel. They are never a
        # routing target, which is why they are capped rather than listed.
        f"brands: {_join(document.get('brands'))[:CARD_BRANDS_MAX] or 'none'}",
        f"products: {_join(document.get('product_names'))[:CARD_PRODUCTS_MAX] or 'none'}",
        spoken,
    ]
    return " | ".join(line for line in lines if line)


def card_hash(card: str) -> str:
    return hashlib.sha256(card.encode("utf-8")).hexdigest()


def _route_once(card: str, seed: int, system_prompt: str, vocab: dict[str, str]) -> str | None:
    """One vote. Returns a vocabulary term, '' for none, or None on failure."""
    from api_config import get_openai_client

    client = get_openai_client()
    response = client.chat.completions.create(
        model=ROUTE_MODEL,
        temperature=ROUTE_TEMPERATURE,
        max_tokens=ROUTE_MAX_TOKENS,
        seed=seed,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": card},
        ],
    )
    raw = response.choices[0].message.content or "{}"
    try:
        shelf = _text(json.loads(raw).get("shelf"))
    except Exception:
        return ""
    # Anything the model invents is coerced to "no shelf" rather than becoming
    # a new shelf — this is what makes narrow titles unrepresentable.
    return shelf if shelf in vocab else ""


def _cached_route(connection, user_id: str, reel_id: str, hashed: str) -> str | None:
    row = connection.execute(
        """
        SELECT shelf_key FROM collection_routes
        WHERE user_id = ? AND reel_id = ? AND card_hash = ? AND prompt_version = ?
        LIMIT 1
        """,
        (user_id, reel_id, hashed, PROMPT_VERSION),
    ).fetchone()
    return row["shelf_key"] if row else None


def _last_known_route(connection, user_id: str, reel_id: str) -> str | None:
    row = connection.execute(
        """
        SELECT shelf_key FROM collection_routes
        WHERE user_id = ? AND reel_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (user_id, reel_id),
    ).fetchone()
    return row["shelf_key"] if row else None


def rebuild_user_shelves(user_id: str, max_new_routes: int = 400) -> dict:
    """Route every reel, then publish the shelves. Safe to run repeatedly.

    Never call this from a request handler — it talks to OpenAI. It belongs in
    the rebuild_library job.
    """
    from app.services.jobs import is_quota_failure

    ensure_schema()
    vocab = vocabulary_for(user_id)
    system_prompt = route_system_prompt(vocab)
    rows = _reel_rows(user_id)

    labels: dict[str, str] = {}
    rows_by_reel: dict[str, dict] = {}
    llm_calls = 0
    routed_new = 0
    skipped_unroutable = 0
    quota_hit = False

    for row in rows:
        reel_id = str(row["reel_id"])
        card = build_card(row)
        if not card:
            skipped_unroutable += 1
            continue
        rows_by_reel[reel_id] = row
        hashed = card_hash(card)

        with get_connection() as connection:
            cached = _cached_route(connection, user_id, reel_id, hashed)
        if cached is not None:
            labels[reel_id] = cached
            continue

        if quota_hit or routed_new >= max_new_routes:
            with get_connection() as connection:
                fallback = _last_known_route(connection, user_id, reel_id)
            if fallback:
                labels[reel_id] = fallback
            continue

        votes: list[str] = []
        for seed in ROUTE_SEEDS:
            try:
                vote = _route_once(card, seed, system_prompt, vocab)
                llm_calls += 1
            except Exception as exc:
                message = str(exc)
                print(f"[collections] route failed for {reel_id}: {message[:200]}")
                if is_quota_failure(message):
                    quota_hit = True
                    break
                continue
            votes.append(vote)

        if not votes:
            # Nothing decided this round: keep whatever this reel was on before
            # so a dead key produces the previous shelf set, not an empty one.
            with get_connection() as connection:
                fallback = _last_known_route(connection, user_id, reel_id)
            if fallback:
                labels[reel_id] = fallback
            continue

        winner, count = Counter(votes).most_common(1)[0]
        shelf_key = winner if count >= ROUTE_MIN_VOTES else ""
        labels[reel_id] = shelf_key
        routed_new += 1
        with get_connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO collection_routes
                    (user_id, reel_id, card_hash, prompt_version, shelf_key, votes_json, model, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, reel_id, hashed, PROMPT_VERSION, shelf_key, json.dumps(votes), ROUTE_MODEL, _now()),
            )

    counts = Counter(shelf for shelf in labels.values() if shelf)
    ordered = sorted(counts.items(), key=lambda row: (-row[1], row[0]))
    published = [(term, total) for term, total in ordered if total >= MIN_SHELF_MEMBERS][:MAX_SHELVES]
    published_terms = {term for term, _ in published}

    built_at = _now()
    with get_connection() as connection:
        connection.execute("DELETE FROM collection_shelves WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM collection_memberships WHERE user_id = ? AND source = 'router'", (user_id,))
        for rank, (term, total) in enumerate(ordered):
            status = "published" if term in published_terms else "below_floor"
            connection.execute(
                """
                INSERT OR REPLACE INTO collection_shelves
                    (user_id, shelf_key, list_title, parent_title, member_count, status, rank, built_at)
                VALUES (?, ?, ?, '', ?, ?, ?, ?)
                """,
                (user_id, term, term, total, status, rank, built_at),
            )
        for reel_id, shelf_key in labels.items():
            if shelf_key in published_terms:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO collection_memberships
                        (user_id, shelf_key, reel_id, source, created_at)
                    VALUES (?, ?, ?, 'router', ?)
                    """,
                    (user_id, shelf_key, reel_id, built_at),
                )

    return {
        "user_id": user_id,
        "reels_considered": len(rows),
        "unroutable": skipped_unroutable,
        "routed_new": routed_new,
        "llm_calls": llm_calls,
        "quota_hit": quota_hit,
        "shelved": sum(total for _, total in published),
        "published_shelves": [{"shelf": term, "members": total} for term, total in published],
        "below_floor": [{"shelf": term, "members": total} for term, total in ordered if term not in published_terms],
    }


def load_shelf_collections(user_id: str) -> list[dict]:
    """Published shelves for the UI. Pure read — never calls an LLM."""
    ensure_schema()
    from app.services.library import _media_url_from_path

    with get_connection() as connection:
        shelves = connection.execute(
            """
            SELECT shelf_key, list_title, parent_title, member_count
            FROM collection_shelves
            WHERE user_id = ? AND status = 'published'
            ORDER BY rank ASC
            """,
            (user_id,),
        ).fetchall()
        if not shelves:
            return []
        members = connection.execute(
            """
            SELECT
                collection_memberships.shelf_key AS shelf_key,
                reels.id AS reel_id,
                reels.url AS url,
                reels.received_at AS received_at,
                reels.local_video_path AS local_video_path,
                reels.thumbnail_path AS thumbnail_path,
                reels.media_status AS media_status,
                MIN(reel_items.item_name) AS item_name,
                MIN(reel_items.summary) AS summary,
                deep_search_documents.document_json AS document_json
            FROM collection_memberships
            JOIN reels ON reels.id = collection_memberships.reel_id
            LEFT JOIN reel_items ON reel_items.reel_id = reels.id
            LEFT JOIN deep_search_documents ON deep_search_documents.reel_id = reels.id
            WHERE collection_memberships.user_id = ?
            GROUP BY collection_memberships.shelf_key, reels.id
            ORDER BY reels.received_at DESC, reels.id ASC
            """,
            (user_id,),
        ).fetchall()

    items_by_shelf: dict[str, list[dict]] = {}
    for row in members:
        row = dict(row)
        try:
            document = json.loads(row.get("document_json") or "{}")
        except Exception:
            document = {}
        name = _text(row.get("item_name")) or _text(document.get("main_subject")) or "Saved reel"
        if any(marker in name.lower() for marker in _FAIL_MARKERS):
            name = _text(document.get("main_subject")) or "Saved reel"
        items_by_shelf.setdefault(row["shelf_key"], []).append(
            {
                "reel_id": row["reel_id"],
                "name": name,
                "summary": _text(row.get("summary")) or _text(document.get("visual_summary")),
                "url": row.get("url") or "",
                "media_status": row.get("media_status") or "",
                "local_video_path": row.get("local_video_path") or "",
                "local_video_url": _media_url_from_path(row.get("local_video_path") or ""),
                "thumbnail_path": row.get("thumbnail_path") or "",
                "thumbnail_url": _media_url_from_path(row.get("thumbnail_path") or ""),
                "received_at": row.get("received_at") or "",
            }
        )

    collections = []
    for shelf in shelves:
        items = items_by_shelf.get(shelf["shelf_key"], [])
        if not items:
            continue
        collections.append(
            {
                # parent_title stays empty on purpose: the client hides a shelf
                # whose category is a generic bucket and reads the parent
                # first, so an empty parent lets the shelf stand on its name.
                "parent_title": "",
                "list_title": shelf["list_title"],
                "shelf_key": shelf["shelf_key"],
                "items": items,
            }
        )
    return collections
