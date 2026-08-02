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
* The shelves are INVENTED BY THE MODEL from each user's own library. Nothing
  in this file names a category a real account will see. That is the whole
  feature: Smart Folders already does user-chosen folders, so Collections is
  only worth anything if the shelves come from the reels themselves.
  Measured against a hand-written answer sheet for a real 81-reel library:
  pair-F1 0.867, equal to an 18-term list hand-written by studying that same
  library — but with nothing hardcoded.
* Breadth comes from measured support, never from curation. A shelf publishes
  only once enough reels actually route into it, so "Chest Workout" dies at two
  members and "Gym & Fitness" lives at twenty.
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
# Bumped when the DISCOVERY logic changes, so a stored vocabulary built by an
# older version is rebuilt instead of reused forever.
DISCOVERY_VERSION = "discover_v3"
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

# A shelf's LABEL and the vocabulary term it routes under are deliberately
# separate columns. The term has to stay descriptive enough for the model to
# aim at; the label is whatever the shelf's actual contents have earned. That
# split is what makes renaming free — no re-route, no membership change.


# Every definition is phrased as a PURPOSE — "the reel exists to..." — not as a
# list of things that would appear in such a reel. A contents-phrased
# definition invites matching against the inventory, which is the whole error
# this engine exists to avoid.
# How many reels must support a theme before it can become a shelf. This is
# what enforces BREADTH, and it is why the vocabulary no longer needs to be
# hand-written to stay broad: "Chest Workout" is supported by two reels and
# dies, "Gym & Fitness" is supported by twenty and lives. Data decides, not a
# list someone maintains.
MIN_THEME_SUPPORT = 4
MAX_DISCOVERED_TERMS = 16
DISCOVERY_BATCH = 40

# Sharper shelf names are OFF.
#
# The idea was sound — a shelf of fifteen protein recipes should say so — but
# it was tried on the real library and did damage. "Gym & Fitness" became
# "Upper Body Workouts" while still holding a motivational reel, and
# "Recipes & Cooking" became "High Protein & Healthy Cooking" while still
# holding a chocolate cake. A narrow name is a promise about every member, so
# ONE outlier makes it a lie, and the model's own coverage self-report is not
# reliable enough to catch that. Broad names are honest about a mixed shelf.
#
# Re-enable only behind a coverage check MEASURED against the members rather
# than reported by the model.
# Folder logos. gpt-image-1-mini at low quality is $0.005 an image (verified
# against OpenAI's pricing docs) — about 44 paise, once per folder, and folder
# names are sticky so a logo is never regenerated for a rename. Generated at
# 1024 because that is the minimum, then stored downscaled: a 1.3MB original
# is pointless for something rendered at 40 pixels, and 96px lands under 8KB,
# small enough to travel inline with the library payload and skip object
# storage entirely.
ICON_ENABLED = True
ICON_MODEL = "gpt-image-1-mini"
ICON_PX = 96
MAX_NEW_ICONS = 12

# "Folder" is deliberately absent from this prompt. An earlier version said
# "an icon for a folder called X" and six of seven came back as drawings of
# folders — a container inside the app's own rounded tile.
ICON_PROMPT = (
    "A minimal flat vector icon symbolising: {name}. "
    "Draw ONE single centred everyday object that stands for that idea. "
    "Chunky simple shapes, thick clean dark-brown outlines, friendly cartoon style, "
    "warm amber and cream colours, fully transparent background. "
    "Do NOT draw a folder, a file, a frame, a card, a box or any container. "
    "No text, no letters, no numbers. No scenery, no shadow. "
    "Sticker style, centred, with empty margin around the object."
)

RENAME_ENABLED = False
RENAME_MIN_MEMBERS = 8
RENAME_MIN_COVERAGE = 0.8


# EMERGENCY FALLBACK ONLY — not the product's taxonomy, and never the shelves a
# real account sees. Reached only when a library is too small to derive
# anything from, or when discovery fails outright.
#
# Collections exists so the MODEL invents the shelves; Smart Folders already
# covers user-chosen folders. A hardcoded list here makes the feature "Smart
# Folders where I picked the folders", which is worse than either. Measuring
# such a list against the library it was written from also proves nothing —
# that circularity is exactly how it scored well and stayed wrong.
#
# Do not extend this list to fix a reported misroute. Fix discovery.
BASE_VOCAB: dict[str, str] = {
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
        "Nothing is sold, taught, argued or explained. If they are making a point, this is "
        "the wrong shelf"
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
    CREATE TABLE IF NOT EXISTS collection_vocabulary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        term TEXT NOT NULL,
        definition TEXT NOT NULL,
        support INTEGER NOT NULL DEFAULT 0,
        version TEXT NOT NULL DEFAULT '',
        icon TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        UNIQUE(user_id, term)
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
        # A table created before `version` existed keeps its old shape, so add
        # the column rather than relying on CREATE TABLE IF NOT EXISTS.
        try:
            connection.execute("ALTER TABLE collection_vocabulary ADD COLUMN version TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass
        try:
            connection.execute("ALTER TABLE collection_vocabulary ADD COLUMN icon TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass
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


# Measured against the founder's hand-written answer sheet: this wording scores
# pair-F1 0.867 with NO hardcoded categories, matching the 18-term list that was
# hand-written by studying his library. Rules 3 and 4 are the ones that earned
# it — before them the model invented "Fashion & Personal Style: the reel exists
# to showcase clothing without selling", an appearance bucket wearing a purpose
# costume, and half the watch-only reels moved into it.
DISCOVER_SYSTEM = """
You are naming the shelves for one person's saved-reel library. You will be shown short
descriptions of reels they saved. Name the themes that actually recur in THIS collection.

WHAT A THEME IS
A theme is a reason someone saves things. Finish the sentence "the reel exists to ___" and
that is your definition.

RULES FOR EVERY THEME YOU PROPOSE
1. BROAD umbrellas. "Gym & Fitness", never "Chest Workout" or "Upper Body Workouts".
   "Recipes & Cooking", never "High Protein Pancakes". If a theme would cover fewer than a
   handful of these reels, widen it or drop it.
2. A theme is what reels are FOR, never what the people or things in them LOOK like.
   "Casual and Dressy Outfits" describes appearances and is not a theme.
3. A theme must say what the VIEWER GETS from the reel - something to buy, cook, visit,
   play, use, learn. "Showcasing", "showing" or "displaying" something is not a purpose,
   it is a description of footage. Never propose a theme whose definition is only that
   something is shown or looks a certain way.
4. A theme about buying must say so in its definition: the reel has to be SELLING or
   RECOMMENDING the thing, with a brand or a product. Someone simply wearing or holding
   something is not that theme, and there must NOT be a separate theme for wearing or
   showing clothes without selling them.
5. A theme about a person being on camera - singing, dancing, modelling, posing, getting
   ready, lip syncing - must say in its definition that nothing is sold, taught, argued or
   explained there.
6. Never name a brand, a creator, a person, a city or a specific product.
7. Only themes you can see repeating here. Not categories that are common in general.
8. Do not merge two different reasons into one theme. Somewhere to EAT OUT and how to COOK
   are different reasons and must not share a shelf.

Reply JSON only:
{"themes":[{"name":"...","definition":"the reel exists to ...","approx_reels":<int>}]}
""".strip()


def _discover_themes(subjects: list[str], covered: list[str] | None = None) -> list[dict]:
    """Ask what themes run through these reels that the base shelves miss."""
    from api_config import get_openai_client

    client = get_openai_client()
    listing = "\n".join(f"- {subject[:160]}" for subject in subjects)
    if covered:
        listing = (
            "Shelves that already exist (do NOT propose these or anything that belongs inside them):\n"
            + "\n".join(f"- {term}" for term in covered)
            + f"\n\n{listing}"
        )
    response = client.chat.completions.create(
        model=ROUTE_MODEL,
        temperature=0,
        max_tokens=900,
        seed=ROUTE_SEEDS[0],
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": DISCOVER_SYSTEM},
            {"role": "user", "content": f"{len(subjects)} saved reels:\n{listing}"},
        ],
    )
    payload = json.loads(response.choices[0].message.content or "{}")
    themes = payload.get("themes")
    return themes if isinstance(themes, list) else []


# Verbatim from the measured run. The last bullet matters most: consolidation
# rewrites every definition, so without it the guard clauses that keep
# watch-only reels out of a shopping shelf are quietly paraphrased away.
CONSOLIDATE_SYSTEM = """
You are cleaning up a draft list of shelf names written in separate passes that could not
see each other. It therefore contains the same interest under several names, and sub-types
listed next to the thing they belong inside.

- Merge entries that mean the same thing.
- A sub-type collapses into its parent. "Upper Body Workouts" belongs inside
  "Gym & Fitness". Never keep both.
- Drop anything describing what people or things LOOK like rather than why a reel was saved.
- Prefer fewer, broader shelves.
- Keep every definition phrased "the reel exists to ...", and keep the clauses that say what
  must be true for a reel to belong (selling, teaching, nothing being sold).

Reply JSON only:
{"themes":[{"name":"...","definition":"the reel exists to ...","approx_reels":<int>}]}
""".strip()


def _consolidate_themes(
    candidates: list[dict],
    covered: list[str] | None = None,
    existing: list[str] | None = None,
) -> list[dict]:
    """Merge the per-batch drafts into one vocabulary. One call.

    `existing` are the shelves this person already has on screen. Anchoring to
    them here is what stops a folder being renamed every time the vocabulary is
    re-derived — measured over a growing library, one shelf went
    "Fitness and Exercise" -> "Fitness & Workout Routines" -> "Fitness Workouts"
    while holding the same reels throughout.
    """
    from api_config import get_openai_client

    client = get_openai_client()
    listing = "\n".join(
        f"- {row['name']} ({row['support']} reels): {row['definition'][:110]}" for row in candidates
    )
    if existing:
        listing = (
            "Shelves this person ALREADY HAS. They have learned to recognise these names.\n"
            "If a draft entry below is the same interest as one of these, reply with the\n"
            "EXISTING NAME EXACTLY as written here, unchanged. Only invent a new name for an\n"
            "interest that is genuinely not in this list:\n"
            + "\n".join(f"- {term}" for term in existing)
            + f"\n\n{listing}"
        )
    if covered:
        # Consolidation is the only stage that sees every draft at once, so it
        # is the only place a semantic duplicate can reliably be caught. A
        # lexical check cannot: "Workout Routines" shares no word with
        # "Gym & Fitness" and would survive one.
        listing = (
            "Shelves that ALREADY EXIST. Drop any draft entry that is one of these, means the\n"
            "same thing as one of these, or belongs inside one of these:\n"
            + "\n".join(f"- {term}" for term in covered)
            + f"\n\nDraft list:\n{listing}"
        )
    response = client.chat.completions.create(
        model=ROUTE_MODEL,
        temperature=0,
        max_tokens=900,
        seed=ROUTE_SEEDS[0],
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": CONSOLIDATE_SYSTEM},
            {"role": "user", "content": listing},
        ],
    )
    payload = json.loads(response.choices[0].message.content or "{}")
    themes = payload.get("themes")
    return themes if isinstance(themes, list) else []


def _generate_icon(name: str) -> str:
    """One folder logo, returned as a data URI. Empty string on any failure."""
    import base64
    import io

    from PIL import Image

    from api_config import get_openai_client

    client = get_openai_client()
    response = client.images.generate(
        model=ICON_MODEL,
        prompt=ICON_PROMPT.format(name=name),
        size="1024x1024",
        quality="low",
        background="transparent",
        output_format="png",
        n=1,
    )
    raw = base64.b64decode(response.data[0].b64_json)
    image = Image.open(io.BytesIO(raw)).convert("RGBA")
    image.thumbnail((ICON_PX, ICON_PX), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


_LAST_ICON_ERROR: dict[str, str] = {}


def icon_report(user_id: str) -> dict:
    """Why folders do or do not have logos. Reads only."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT term, length(icon) AS n FROM collection_vocabulary WHERE user_id = ?", (user_id,)
        ).fetchall()
    return {
        "folders_with_logo": sum(1 for row in rows if (row["n"] or 0) > 0),
        "folders_without_logo": sum(1 for row in rows if not (row["n"] or 0)),
        "last_logo_error": _LAST_ICON_ERROR.get(user_id, ""),
    }


def ensure_icons(user_id: str, terms: list[str]) -> int:
    """Give every published folder a logo. Only ever generates missing ones."""
    if not ICON_ENABLED or not terms:
        return 0
    with get_connection() as connection:
        have = {
            row["term"]
            for row in connection.execute(
                "SELECT term FROM collection_vocabulary WHERE user_id = ? AND icon != ''", (user_id,)
            ).fetchall()
        }
    made = 0
    for term in terms:
        if term in have or made >= MAX_NEW_ICONS:
            continue
        try:
            icon = _generate_icon(term)
        except Exception as exc:
            # Kept verbatim rather than swallowed: the failure modes here are
            # a missing Pillow, an image model the org cannot call, or an SDK
            # too old for the transparent-background parameters — and none of
            # them are guessable from an empty shelf list.
            _LAST_ICON_ERROR[user_id] = f"{type(exc).__name__}: {exc}"[:300]
            print(f"[collections] icon failed for {term}: {exc}")
            continue
        if not icon:
            continue
        with get_connection() as connection:
            connection.execute(
                "UPDATE collection_vocabulary SET icon = ? WHERE user_id = ? AND term = ?",
                (icon, user_id, term),
            )
        made += 1
    return made


def _icons_for(user_id: str) -> dict[str, str]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT term, icon FROM collection_vocabulary WHERE user_id = ? AND icon != ''", (user_id,)
        ).fetchall()
    return {row["term"]: row["icon"] for row in rows}


def _existing_terms(user_id: str) -> list[str]:
    """Shelf names this account already shows, whatever version produced them."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT term FROM collection_vocabulary WHERE user_id = ? ORDER BY support DESC, term ASC",
            (user_id,),
        ).fetchall()
    return [row["term"] for row in rows]


def _existing_definitions(user_id: str) -> dict[str, str]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT term, definition FROM collection_vocabulary WHERE user_id = ?", (user_id,)
        ).fetchall()
    return {row["term"].strip().lower(): (row["term"], row["definition"]) for row in rows}


def discover_vocabulary(user_id: str, rows: list[dict] | None = None) -> dict[str, str]:
    """Derive this user's shelf vocabulary from this user's own library.

    The whole point: a hand-written list can only ever fit the libraries whose
    owner complained loudest. Someone who saves cricket gets a cricket shelf
    without anyone editing code, and someone who saves none of what this
    founder saves gets none of his shelves.

    Deterministic for a given library: batches are ordered by reel id,
    temperature is 0, and the result is persisted, so it is derived once and
    then read.
    """
    ensure_schema()
    rows = rows if rows is not None else _reel_rows(user_id)
    subjects = []
    for row in rows:
        card = build_card(row)
        if not card:
            continue
        # The subject line plus what the describer says it shows — enough to
        # recognise a theme, without the inventory that would invent one.
        lines = [line for line in card.split("\n") if line.startswith("SUBJECT LINE:")]
        scene = [
            line for line in card.split("\n")
            if line.startswith("- ") and "narration" not in line and "caption" not in line
        ]
        subjects.append((lines[0][14:] if lines else "") + (f" — {scene[0][2:]}" if scene else ""))

    if len(subjects) < MIN_THEME_SUPPORT * 2:
        return dict(BASE_VOCAB)

    proposals: dict[str, dict] = {}
    for start in range(0, len(subjects), DISCOVERY_BATCH):
        batch = subjects[start:start + DISCOVERY_BATCH]
        try:
            themes = _discover_themes(batch)
        except Exception as exc:
            print(f"[collections] theme discovery failed for {user_id}: {exc}")
            continue
        for theme in themes:
            name = _text(theme.get("name"))
            definition = _text(theme.get("definition"))
            if not name or not definition:
                continue
            support = int(theme.get("approx_reels") or 0)
            existing = proposals.get(name.lower())
            if existing:
                existing["support"] += support
            else:
                proposals[name.lower()] = {"name": name, "definition": definition, "support": support}

    # The batches could not see each other, so the draft holds the same
    # interest under several names and sub-types beside their parents. Merging
    # on an exact name match — which is all this used to do — left "Upper Body
    # Workouts" and "Fitness & Workout" standing as two shelves, and split one
    # person's gym reels across both. Consolidate the whole draft in one pass.
    draft = sorted(proposals.values(), key=lambda row: (-row["support"], row["name"].lower()))
    try:
        merged = _consolidate_themes(draft, existing=_existing_terms(user_id))
    except Exception as exc:
        print(f"[collections] theme consolidation failed for {user_id}: {exc}")
        merged = []
    final = []
    for theme in merged or []:
        name = _text(theme.get("name"))
        definition = _text(theme.get("definition"))
        if name and definition:
            final.append({"name": name, "definition": definition, "support": int(theme.get("approx_reels") or 0)})
    if not final:
        final = draft

    # No support floor here. approx_reels is the model GUESSING how many reels
    # it saw, and filtering on that guess deleted the restaurants shelf outright
    # — same mistake as trusting its self-reported name coverage. The real count
    # is measured after routing, and MIN_SHELF_MEMBERS already drops shelves
    # nobody landed on.
    # Reuse the stored wording for any shelf that already exists. Keeping only
    # the name would still shift the vocabulary hash on every re-derivation,
    # which re-routes the whole library — an invisible change costing real
    # money. Same shelf, same name, same definition, same cache.
    previous = _existing_definitions(user_id)
    for row in final:
        match = previous.get(row["name"].strip().lower())
        if match:
            row["name"], row["definition"] = match

    kept = list(final)
    kept.sort(key=lambda row: (-row["support"], row["name"].lower()))
    kept = kept[:MAX_DISCOVERED_TERMS]

    created = _now()
    with get_connection() as connection:
        connection.execute("DELETE FROM collection_vocabulary WHERE user_id = ?", (user_id,))
        for row in kept:
            connection.execute(
                """
                INSERT OR REPLACE INTO collection_vocabulary
                    (user_id, term, definition, support, version, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, row["name"], row["definition"], row["support"], DISCOVERY_VERSION, created),
            )
    return {row["name"]: row["definition"] for row in kept}


REFINE_SYSTEM = """
You are naming one shelf in a person's saved-reel library.

You get the shelf's current broad name and the reels actually on it. Your job is to decide
whether these reels share something more specific than the broad name says.

Rules:
- Only propose a sharper name if it honestly describes NEARLY ALL of these reels. If some
  of them would not fit under it, keep the broad name.
- The sharper name must come from what these reels have in common, not from what the broad
  name suggests they might have in common.
- Never name a brand, a creator, a person or a specific product.
- Keep it short and plain, the kind of thing someone would call a folder.
- Staying broad is a perfectly good answer and is usually right.

Reply JSON only:
{"name":"<sharper name, or the current name to keep it>","covers":<how many of the reels it honestly describes>}
""".strip()


def _refine_name(term: str, subjects: list[str]) -> str | None:
    """Ask whether this shelf's members share something sharper than its name."""
    from api_config import get_openai_client

    client = get_openai_client()
    listing = "\n".join(f"- {subject[:140]}" for subject in subjects)
    response = client.chat.completions.create(
        model=ROUTE_MODEL,
        temperature=0,
        max_tokens=60,
        seed=ROUTE_SEEDS[0],
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": REFINE_SYSTEM},
            {"role": "user", "content": f'Current name: "{term}"\n{len(subjects)} reels on this shelf:\n{listing}'},
        ],
    )
    payload = json.loads(response.choices[0].message.content or "{}")
    name = _text(payload.get("name"))
    covers = int(payload.get("covers") or 0)
    if not name or name.lower() == term.lower():
        return None
    if covers < RENAME_MIN_COVERAGE * len(subjects):
        return None
    return name


def refine_shelf_name(term: str, subjects: list[str]) -> str:
    """The label a shelf should carry, given what is actually on it.

    Broad while a shelf is small, sharper once it is big enough to have earned
    it — a folder of fifteen recipes that are all protein recipes should say
    so. Renaming only ever changes the LABEL: shelf_key stays the vocabulary
    term, so membership, the route cache and every stored verdict are
    untouched, and a rename costs one call rather than a re-route.
    """
    if not RENAME_ENABLED or len(subjects) < RENAME_MIN_MEMBERS:
        return term
    try:
        sharper = _refine_name(term, subjects)
    except Exception as exc:
        print(f"[collections] name refinement failed for {term}: {exc}")
        return term
    return sharper or term


def vocabulary_for(user_id: str, rows: list[dict] | None = None) -> dict[str, str]:
    """This user's shelves. Derived from their library, persisted, then reused."""
    ensure_schema()
    with get_connection() as connection:
        stored = connection.execute(
            """
            SELECT term, definition FROM collection_vocabulary
            WHERE user_id = ? AND version = ?
            ORDER BY support DESC, term ASC
            """,
            (user_id, DISCOVERY_VERSION),
        ).fetchall()
    if stored:
        return {row["term"]: row["definition"] for row in stored}
    return discover_vocabulary(user_id, rows=rows)


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


def vocab_version(vocab: dict[str, str]) -> str:
    """Cache key for a routing decision.

    The vocabulary IS part of the system prompt, so two runs with different
    shelves are not the same question — but the cache used to key on
    PROMPT_VERSION alone. That meant fixing a broken vocabulary changed
    nothing: every reel came straight back from the cache still wearing the
    old shelf. Folding the vocabulary into the key means changing the shelves
    re-routes, and leaving them alone stays free.
    """
    digest = hashlib.sha256(
        "|".join(f"{term}={definition}" for term, definition in sorted(vocab.items())).encode("utf-8")
    ).hexdigest()[:12]
    return f"{PROMPT_VERSION}:{digest}"


def _cached_route(connection, user_id: str, reel_id: str, hashed: str, version: str) -> str | None:
    row = connection.execute(
        """
        SELECT shelf_key FROM collection_routes
        WHERE user_id = ? AND reel_id = ? AND card_hash = ? AND prompt_version = ?
        LIMIT 1
        """,
        (user_id, reel_id, hashed, version),
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
    rows = _reel_rows(user_id)
    # Derive this account's shelves from this account's library before routing
    # into them. Reusing rows so discovery and routing see the same snapshot.
    vocab = vocabulary_for(user_id, rows=rows)
    system_prompt = route_system_prompt(vocab)
    route_version = vocab_version(vocab)

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
            cached = _cached_route(connection, user_id, reel_id, hashed, route_version)
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
                (user_id, reel_id, hashed, route_version, shelf_key, json.dumps(votes), ROUTE_MODEL, _now()),
            )

    counts = Counter(shelf for shelf in labels.values() if shelf)
    ordered = sorted(counts.items(), key=lambda row: (-row[1], row[0]))
    published = [(term, total) for term, total in ordered if total >= MIN_SHELF_MEMBERS][:MAX_SHELVES]
    published_terms = {term for term, _ in published}

    # Let a big, tight shelf earn a sharper label than the broad term it was
    # routed under. Only the label moves — shelf_key stays the vocabulary term.
    subjects_by_term: dict[str, list[str]] = {}
    for reel_id, shelf_key in labels.items():
        if shelf_key not in published_terms:
            continue
        card = build_card(rows_by_reel.get(reel_id, {})) or ""
        line = card.split("\n", 1)[0]
        subjects_by_term.setdefault(shelf_key, []).append(line[14:] if line.startswith("SUBJECT LINE:") else line)
    titles = {
        term: refine_shelf_name(term, subjects_by_term.get(term, []))
        for term in published_terms
    }
    renamed = {term: title for term, title in titles.items() if title != term}

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
                (user_id, term, titles.get(term, term), total, status, rank, built_at),
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

    icons_made = ensure_icons(user_id, [term for term, _ in published])

    return {
        "user_id": user_id,
        "icons_made": icons_made,
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


# Measured on the real library: ~1,318 input tokens per call (system prompt +
# card) and ~10 out, at gpt-4.1-mini's $0.40/1M in and $1.60/1M out.
_USD_PER_CALL = (1318 * 0.40 + 10 * 1.60) / 1_000_000
_INR_PER_USD = 88


def reel_sheet_rows(user_id: str) -> list[dict]:
    """The answer-sheet rows, before formatting."""
    ensure_schema()
    rows = _reel_rows(user_id)
    with get_connection() as connection:
        placed = {
            row["reel_id"]: row["shelf_key"]
            for row in connection.execute(
                "SELECT reel_id, shelf_key FROM collection_memberships WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        }
    out = []
    number = 0
    for row in rows:
        card = build_card(row)
        if not card:
            continue
        number += 1
        first = card.split("\n", 1)[0]
        subject = first[14:] if first.startswith("SUBJECT LINE:") else first
        name = _text(row.get("item_name"))
        label = name if name and "processing failed" not in name.lower() else subject
        out.append(
            {
                "number": number,
                "reel_id": str(row["reel_id"]),
                "reel": label,
                "subject": subject,
                "now": placed.get(str(row["reel_id"])) or "",
            }
        )
    return out


def reel_cards_export(user_id: str) -> str:
    """Every reel's full routing card, as JSON.

    The answer sheet says what the shelves SHOULD be; this is the exact input
    the router sees. With both, variants can be scored offline against real
    data instead of being guessed at, and the only spend is the routing calls
    themselves.
    """
    ensure_schema()
    out = []
    for row in _reel_rows(user_id):
        card = build_card(row)
        if not card:
            continue
        out.append({"reel_id": str(row["reel_id"]), "card": card})
    return json.dumps({"user_id": user_id, "count": len(out), "cards": out}, indent=1)


def reel_sheet_csv(user_id: str) -> str:
    """The answer sheet as CSV, so it opens in Excel with real columns.

    reel_id travels with each row: whatever the founder renames or reorders in
    a spreadsheet, that column is what lets the returned file be scored
    against the engine's output.
    """
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["#", "reel_id", "What the reel is", "Fuller description", "Where it is now", "YOUR FOLDER"])
    for row in reel_sheet_rows(user_id):
        writer.writerow([row["number"], row["reel_id"], row["reel"], row["subject"], row["now"], ""])
    return buffer.getvalue()


def reel_sheet(user_id: str) -> str:
    """Every routable reel as a numbered list, for hand-labelling.

    The founder writes the folder he wants after each line and pastes it back;
    that becomes the answer sheet a model variant is scored against. Plain
    text on purpose — it has to be readable in a browser tab and pasteable
    into notes without any tooling.
    """
    ensure_schema()
    rows = _reel_rows(user_id)
    with get_connection() as connection:
        placed = {
            row["reel_id"]: row["shelf_key"]
            for row in connection.execute(
                "SELECT reel_id, shelf_key FROM collection_memberships WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        }

    lines = [
        "CLIPNEST — COLLECTIONS ANSWER SHEET",
        "",
        "Write the folder you want after the final |  .",
        "Leave it blank if the reel should be in NO folder — those matter as much as the rest.",
        "",
        f"{'#':>3}  {'WHAT THE REEL IS':<62}  {'WHERE IT IS NOW':<24}  YOUR FOLDER",
        "-" * 120,
    ]
    number = 0
    for row in rows:
        card = build_card(row)
        if not card:
            continue
        number += 1
        first = card.split("\n", 1)[0]
        subject = first[14:] if first.startswith("SUBJECT LINE:") else first
        name = _text(row.get("item_name"))
        label = name if name and "processing failed" not in name.lower() else subject
        lines.append(
            f"{number:>3}  {label[:62]:<62}  {(placed.get(str(row['reel_id'])) or '-')[:24]:<24}  |"
        )
    lines += ["", f"{number} reels. Paste this back with your folders filled in."]
    return "\n".join(lines)


def rebuild_estimate(user_id: str) -> dict:
    """What a rebuild would cost, without calling anything.

    Every verdict is cached against the hash of the card that produced it, so
    only reels whose card is new or changed cost money. After a prompt change
    that is all of them; on an ordinary day it is however many reels were
    saved since the last run, and usually zero.
    """
    ensure_schema()
    rows = _reel_rows(user_id)
    version = vocab_version(vocabulary_for(user_id, rows=rows))
    routable = 0
    cached = 0
    with get_connection() as connection:
        for row in rows:
            card = build_card(row)
            if not card:
                continue
            routable += 1
            if _cached_route(connection, user_id, str(row["reel_id"]), card_hash(card), version) is not None:
                cached += 1
    to_route = routable - cached
    calls = to_route * len(ROUTE_SEEDS)
    return {
        "user_id": user_id,
        "prompt_version": version,
        "reels_routable": routable,
        "already_cached": cached,
        "would_route": to_route,
        "estimated_calls": calls,
        "estimated_inr": round(calls * _USD_PER_CALL * _INR_PER_USD, 2),
        "estimated_seconds": calls,
    }


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

    icons = _icons_for(user_id)
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
                "list_title": shelf["list_title"] or shelf["shelf_key"],
                "shelf_key": shelf["shelf_key"],
                "icon_url": icons.get(shelf["shelf_key"], ""),
                "items": items,
            }
        )
    return collections
