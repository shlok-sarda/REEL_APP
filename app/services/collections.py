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
import threading
import time
from collections import Counter

from app.db.database import get_connection


PROMPT_VERSION = "shelves_v4"
ROUTE_MODEL = "gpt-4.1-mini"
ROUTE_SEEDS = (7, 8, 9)
ROUTE_TEMPERATURE = 0
ROUTE_MAX_TOKENS = 25

# Unanimous. Two-of-three let through everything the model was merely leaning
# towards, and "leaning towards" is exactly the reel that has no clear intent.
# Raising this trades coverage for precision, which is the trade the founder
# asked for: he does not care how many reels end up on a shelf.
ROUTE_MIN_VOTES = 3

# Three, not five. The unit here is a REEL, so a single caption listicle can no
# longer manufacture a shelf out of its own twelve items — that was what forced
# the old floor up, and the old floor is what killed "Restaurants in Goa" at
# four members with perfect purity.
MIN_SHELF_MEMBERS = 3
MAX_SHELVES = 12

# reel_7's transcript is 43 chars of small talk; the median real transcript in
# the library is 621. The boundary sits an order of magnitude from both.
TRANSCRIPT_INCIDENTAL_CHARS = 80
# The creator's own words are purpose evidence — unlike everything the
# describer wrote, the creator chose to say it. Hashtags are stripped: they are
# reach tactics, not statements of purpose.
CARD_CAPTION_MAX = 220

_FAIL_MARKERS = ("processing failed", "could not be processed", "failed reels")

# What a shelf is CALLED on screen, separate from the vocabulary term the model
# routes with. The term has to stay descriptive enough for the model to aim at;
# the label the user reads should just be plain. Keeping them apart means a
# rename is a display change and never re-routes a single reel.
SHELF_DISPLAY_NAMES = {
    "People & Performance": "People",
}


# Every definition is phrased as a PURPOSE — "the reel exists to..." — not as a
# list of things that would appear in such a reel. A contents-phrased
# definition invites matching against the inventory, which is the whole error
# this engine exists to avoid.
CORE_VOCAB: dict[str, str] = {
    "Food & Restaurants": "the reel exists to show you something to eat or somewhere to eat it",
    "Recipes & Cooking": "the reel exists to teach you how to make something",
    "Travel & Places": "the reel exists to sell you on going somewhere: a destination, a stay, a trip",
    "Gym & Fitness": "the reel exists to teach or show training, exercise or sport technique",
    "Gadgets & Tech": "the reel exists to show you a device: a review, a demo, a repair, a thing to buy",
    "Apps & AI Tools": "the reel exists to show you software worth using",
    "Fashion & Shopping": "the reel exists to make you want to buy something to wear or own",
    "Grooming & Personal Care": "the reel exists to teach a hair, skin or grooming routine or product",
    "Movies & Shows": "the reel exists to discuss, recommend or clip a film or series",
    "Money & Career": "the reel exists to advise on work, business, study, money or making money",
    "People & Performance": (
        "the reel exists for the person on camera: their performance, their look, the edit. "
        "It teaches nothing and sells nothing"
    ),
    "Home & Decor": "the reel exists to show furniture, lighting or how a space is styled",
    "Cars & Rides": "the reel exists to show a car, bike or vehicle",
    "Music": "the reel exists for a song, an artist, an instrument or music gear",
    "Books & Reading": "the reel exists for a book or for reading",
    "Pets & Animals": "the reel exists for an animal",
    "Art & Design": "the reel exists to show art, illustration or design work",
    "Hobbies & Collecting": "the reel exists for a hobby object or a collection",
}


# No rule here names a domain, a garment, a shelf or any specific failure. Each
# is a test about what the EVIDENCE means: who wrote it, whether it merely
# repeats itself, whether it is a container, whether it is swappable.
#
# The old "ACTIVITY BEATS APPEARANCE" rule is deleted rather than rewritten. It
# was the leak: any incidental the describer happened to phrase as a verb
# outranked every guard below it.
_ROUTE_RULES = """
A shelf is a claim about WHY the reel exists and why someone saved it. It is never a claim
about what happened to be in the video.

HOW TO READ THIS CARD
Everything under WHAT IS PRESENT IN IT was written by an automatic describer whose only job
is to name what it can see and hear. It names things whether or not they matter. A thing
being listed there tells you it was present. It tells you NOTHING about why the reel was
made. PRESENCE IS NOT ABOUTNESS.
The SUBJECT LINE comes from the same describer, so read it the same way: take the ONE thing
the reel is built around, and treat the rest of the line - what someone wore, where it was
shot, what was in the background, whatever happened to be named - as circumstance, exactly
as if it had been listed below.
The describer also repeats itself: the same circumstance can appear in the subject line, in
the scene and in the lists. Repetition is not corroboration. One fact written down three
times is still one fact, and it is still circumstance.
The describer's one-sentence account of what the reel shows can state why the reel exists, or
it can only state where and how it was filmed. Take from it what the reel is offering the
viewer; ignore whatever only says what the scene looked like.
WHAT THE REEL DOES reports purpose directly and is never merely circumstance.

DECIDING
1. Finish this sentence: "this reel exists in order to ___." Fill it from the one central
thing plus the purpose evidence, and from nothing else. Then pick the shelf whose
definition matches that sentence. If the only honest ending is "show this person" or "show
this moment", it is the shelf for a person or a moment, or none.
2. A shelf that promises something to buy, visit, use, cook, watch or learn asserts that
the reel is offering it. If nobody speaks and nothing is being presented, then nobody is
offering anything, however many nameable things are present.
3. CONTAINER TEST. When the card names a specific thing and also the larger thing that
merely contains it - the area a place sits inside, the field a tool belongs to, the person
wearing or holding an object, the topic an example illustrates - shelve the specific thing.
Never shelve the container.
4. SWAP TEST. If a named thing could be swapped for another of its kind and the reel would
still make exactly the same point, then it is an example, not the subject. Shelve the point
the reel is making, not the example it reached for.
5. "none" is always allowed and is usually right. Most saved reels belong on no shelf.
Never stretch a reel to fill a shelf. If you are unsure whether ANY shelf applies, answer
"none".
6. When two shelves both fit, take the one that names the specific kind of thing the reel
is about, not the one that names the general situation it happens to sit in. A place you
would eat at is a place to eat, even though it is also somewhere you could travel to.
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
        "You sort a person's saved Instagram reels onto BROAD shelves.\n"
        "Each card below describes ONE reel.\n\n"
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


def _listed(values, limit: int = 6, item_chars: int = 48) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        value = _text(value)
        if not value or value == "{}" or value.lower() in seen:
            continue
        seen.add(value.lower())
        out.append(value[:item_chars])
        if len(out) == limit:
            break
    return "; ".join(out)


def build_card(row: dict) -> str | None:
    """Compress a reel into the only representation the router ever sees.

    The card is organised by what each piece of evidence MEANS, not by which
    column it came from. Everything an automatic describer wrote is grouped
    and labelled as presence; the two things it did not write — how much
    anyone actually speaks, and the creator's own caption — are grouped as
    purpose. That typing is the entire fix: withholding fields does not work,
    because the incidental survives inside the subject sentence, which cannot
    be dropped. Measured 0.805 vs 0.728 accuracy against hand-labelled reels,
    paired McNemar p=0.0026 over three independent seed triples.

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

    subject = _text(document.get("main_subject")) or item_name
    scene = _text(document.get("visual_theme")) or summary
    if not (subject or scene):
        return None

    kind = _text(row.get("main_subject_type")) or "unknown"

    spoken_chars = len(document.get("transcript") or "")
    if spoken_chars == 0:
        narration = "nobody speaks"
    elif spoken_chars < TRANSCRIPT_INCIDENTAL_CHARS:
        narration = "a few words only, nothing explained"
    else:
        narration = f"someone talks through it ({spoken_chars} characters of speech)"

    caption = _text(document.get("caption"))
    caption = " ".join(word for word in caption.split() if not word.startswith("#"))[:CARD_CAPTION_MAX]

    lines = [
        f"SUBJECT LINE: {subject or '(none given)'}",
        f"SUBJECT KIND: {kind}",
        "",
        "WHAT THE REEL DOES (purpose evidence):",
        f"- narration: {narration}",
        f"- creator's own caption: {caption or '(none)'}",
        "",
    ]
    if scene:
        lines += [
            "WHAT THE DESCRIBER SAYS IT SHOWS (may state the point, may only state the setting):",
            f"- {scene}",
            "",
        ]

    # Products and brands are back in the card, but typed as inventory. The
    # previous attempt withheld them and keyed on brand presence instead,
    # which just swapped one presence rule for another and could not touch a
    # reel that names neither.
    lines += ["WHAT IS PRESENT IN IT (inventory - presence only, never a purpose):"]
    things = _listed(document.get("visual_entities"))
    if things:
        lines.append(f"- things visible: {things}")
    named = _listed(list(document.get("brands") or []) + list(document.get("product_names") or []))
    if named:
        lines.append(f"- names and brands recorded: {named}")
    place = _listed(document.get("locations"), limit=4)
    if place:
        lines.append(f"- place recorded: {place}")

    return "\n".join(lines)


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

        if len(votes) < len(ROUTE_SEEDS):
            # A partial vote set must never be decided on. Quota failures break
            # the seed loop mid-reel, and because collection_routes is
            # write-once, persisting "not unanimous" here would strand that
            # reel off the shelves forever — even after the key is restored.
            # Keep whatever it was on before and write nothing.
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


_REBUILD_LOCK = threading.Lock()
_REBUILD_IN_FLIGHT: set[str] = set()


def rebuild_status(user_id: str) -> bool:
    with _REBUILD_LOCK:
        return user_id in _REBUILD_IN_FLIGHT


def start_shelf_rebuild(user_id: str) -> dict:
    """Kick routing off on a background thread and return immediately.

    Deliberately does NOT go through the job queue. A rebuild_library job runs
    the whole legacy processor first, and on a real library that script blows
    past its 600s timeout, fails the job and returns — which meant the shelves
    could never build no matter how many times a rebuild was triggered.
    Routing reads deep_search_documents and writes its own tables; it needs
    none of that pipeline.

    Cheap to call repeatedly: every verdict is cached against the hash of the
    card that produced it, so a second run issues zero API calls.
    """
    ensure_schema()
    with _REBUILD_LOCK:
        if user_id in _REBUILD_IN_FLIGHT:
            return {"ok": True, "started": False, "reason": "a rebuild is already running"}
        _REBUILD_IN_FLIGHT.add(user_id)

    def run() -> None:
        try:
            summary = rebuild_user_shelves(user_id)
            print(f"[collections] {user_id}: {summary['shelved']} reels on "
                  f"{len(summary['published_shelves'])} shelves, {summary['llm_calls']} llm calls")
        except Exception as exc:
            print(f"[collections] rebuild failed for {user_id}: {exc}")
        finally:
            with _REBUILD_LOCK:
                _REBUILD_IN_FLIGHT.discard(user_id)

    threading.Thread(target=run, name=f"shelf-rebuild-{user_id}", daemon=True).start()
    return {
        "ok": True,
        "started": True,
        "note": "Routing runs in the background. Poll /library/status and watch routes_stored climb.",
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
                "list_title": SHELF_DISPLAY_NAMES.get(shelf["shelf_key"], shelf["list_title"]),
                "shelf_key": shelf["shelf_key"],
                "items": items,
            }
        )
    return collections
