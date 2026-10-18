"""Reels that say "comment LINK to get the link".

A creator asks viewers to comment (or DM) one word and promises something back:
a link, a recipe, a PDF, a discount code. Shlok wants these reels collected so
he can fetch the promised thing by hand and later hand it to users directly.
Nothing here is shown to users.

Reads only text the pipeline already extracted (caption, transcript, on-screen
text). No AI call, no cost. A wrong tag is worse than a missed one, so a hit
needs BOTH a specific word to send and something promised back; "comment
below" or "comment your favourite" never counts.

Every word list lives in the block below. Bump DETECTOR_VERSION after editing
it: the next deploy then rescans every saved reel once.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from app.db.database import get_connection

DETECTOR_VERSION = "v2"

# --- Word lists. Edit here, then bump DETECTOR_VERSION. ----------------------

# Asking for a comment. Only when "comment" is the verb: "the pinned comment"
# or "my comment" is a noun and is skipped by NOUN_BEFORE_COMMENT.
COMMENT_VERBS = [r"comment", r"comments", r"commment"]
# Words that also need "below" / "in the comments" right after the trigger,
# since on their own they are too common ("this type of", "drop a like").
COMMENT_CONTEXT_VERBS = [r"type", r"write", r"drop", r"reply", r"reply with", r"leave"]
# Asking for a DM. The trigger word itself is the request for something back.
DM_VERBS = [r"dm", r"dm me", r"send me", r"message me", r"text me", r"inbox me"]
NOUN_BEFORE_COMMENT = [
    "the", "a", "an", "my", "your", "this", "that", "pinned", "first", "top",
    "each", "every", "any", "in", "on", "of", "per", "no", "one", "his", "her",
]
# Hinglish: "LINK comment karo", "recipe comment kardo", "comment mein PDF likho".
HINGLISH_AFTER = [
    r"comment\s+(?:karo|kardo|kar\s+do|karein|karen|kariye|karna|kro|krdo|kr\s+do)",
    r"(?:comment|comments)\s+(?:me|mein|mai|main|box\s+me|box\s+mein)\s+(?:likho|likhiye|likh\s+do|daalo|dalo|bhejo)",
    r"likh\s+(?:do|dena)",
    r"dm\s+(?:karo|kardo|kar\s+do|karein|karen|kro)",
]

# What can be promised, and the words that name it. The first matching group
# wins, so the order matters only where a word could fit two.
PROMISES = {
    "recipe": ["recipe", "recipes", "ingredients", "ingredient"],
    "link": ["link", "links", "url", "lnk"],
    "code": ["code", "discount", "coupon", "promo", "promocode", "offer", "deal", "deals"],
    "file": [
        "pdf", "guide", "ebook", "e-book", "book", "file", "files", "template", "templates",
        "checklist", "notes", "sheet", "spreadsheet", "doc", "document", "workbook", "plan",
        "planner", "itinerary", "presets", "preset", "cheatsheet", "roadmap", "resources",
        "resource", "course", "workout", "routine", "diet", "prompt", "prompts", "script",
    ],
    "list": ["list", "lists"],
    "product": ["product", "products", "details", "price", "outfit", "shop", "buy", "size"],
}

# Phrases that say "you get something back". Used when the trigger word does
# not name the thing (e.g. "comment YES and I'll send you the link").
PROMISE_CUES = [
    r"i(?:'|’)?ll\s+(?:send|dm|share|message|drop|inbox)",
    r"i\s+will\s+(?:send|dm|share|message|drop|inbox)",
    r"(?:will|gonna|going\s+to)\s+(?:send|dm|share)",
    r"(?:send|sending|dm|share)\s+(?:it|you|u|them|the|this)\b",
    r"to\s+(?:get|receive|grab|unlock)",
    r"(?:get|receive)\s+(?:it|the|this|my|a|your|free)\b",
    r"you(?:'|’)?ll\s+(?:get|receive)",
    r"(?:in|to|into)\s+(?:your|ur)\s+(?:dm|dms|inbox)",
    r"straight\s+to\s+your",
    r"for\s+(?:the|my|a|free)\s+(?:\w+\s+){0,2}(?:" + "|".join(w for ws in PROMISES.values() for w in ws) + r")\b",
    r"bhej\s*(?:dunga|dungi|doonga|denge|deta|deti|du|dun)",
    r"bhej(?:ta|ti|\s+raha|\s+rahi)\s+(?:hoon|hu|hun)",
    r"send\s+kar\s*(?:dunga|dungi|denge|du)",
    r"dm\s+kar\s*(?:dunga|dungi|denge|du)",
    r"(?:mil|milega|milegi|mil\s+jayega|mil\s+jaegi|mil\s+jayegi)\b",
    r"inbox\s+(?:me|mein)",
]

# Right after a plain, unquoted word, one of these makes it a trigger anyway:
# "comment emergent, I'll send you the link", "Comment Breakfast to receive
# the recipe". It has to follow within a few words, or it is ordinary speech.
STRONG_CUES = [
    r"(?:i|we)(?:'|’)?ll\s+(?:send|dm|share|slide|message)",
    r"(?:i|we)\s+will\s+(?:send|dm|share|message)",
    r"to\s+(?:get|receive|unlock)\s+(?:the|my|a|your|free|it)\b",
    r"for\s+(?:the|a|my)\s+(?:complete\s+|full\s+|free\s+)?(?:recipe|link|links|pdf|guide|list|code)\b",
]

# Never a trigger word, even in capitals or quotes.
STOP_TRIGGERS = {
    "below", "down", "here", "now", "your", "you", "yes", "no", "the", "a", "an", "if",
    "what", "which", "this", "that", "it", "me", "in", "on", "with", "and", "for", "us",
    "karo", "kardo", "below.", "section", "box", "please", "pls", "plz", "and",
    "who", "how", "why", "when", "where", "favourite", "favorite", "thoughts", "opinion",
    "fast", "first", "back", "them", "him", "her", "my", "our", "more", "something",
    "anything", "one", "two", "done", "ok", "okay", "love", "like", "share", "follow",
    "save", "tag", "mein", "me", "se", "ke", "ki", "ka", "or", "to", "is", "be", "i",
}

# --- End of word lists. ------------------------------------------------------

_PROMISE_OF = {w: kind for kind, words in PROMISES.items() for w in words}
_EMOJI = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200d]")
_QUOTES = "\"'“”‘’«»„`*"
# The word to send: quoted, or a bare word. Quotes may be any of _QUOTES.
_WORD = r"[\"'“”‘’«»„`*]{0,2}\s*([A-Za-z][A-Za-z0-9\-]{1,24})\s*[\"'“”‘’«»„`*]{0,2}"
# "comment the word X", "comment below X", "comment karo X".
_THE_WORD = r"(?:(?:down\s+below|below|down|karo|kardo|kar\s+do)\s+)?(?:the\s+word\s+|word\s+|with\s+)?"
_AFTER_COMMENT_CONTEXT = re.compile(
    r"^[\s,.!:]*(?:below|down\s+below|in\s+(?:the\s+)?comments?|in\s+comments?|as\s+a\s+comment|comment)",
    re.I,
)
_STRONG_RE = re.compile(r"^[\s,.!:\-]{0,4}(?:and\s+|&\s+|aur\s+)?(?:" + "|".join(STRONG_CUES) + r")", re.I)
_CUE_RE = re.compile("|".join(f"(?:{c})" for c in PROMISE_CUES), re.I)
_NOUN_BEFORE = re.compile(r"(?:^|\W)(?:" + "|".join(NOUN_BEFORE_COMMENT) + r")\s*$", re.I)


def _alt(words: list[str]) -> str:
    return "|".join(sorted(words, key=len, reverse=True))


_COMMENT_RE = re.compile(r"\b(" + _alt(COMMENT_VERBS) + r")\b[\s:\-]*" + _THE_WORD + _WORD, re.I)
_CONTEXT_RE = re.compile(r"\b(" + _alt(COMMENT_CONTEXT_VERBS) + r")\b[\s:\-]*" + _THE_WORD + _WORD, re.I)
_DM_RE = re.compile(r"\b(" + _alt(DM_VERBS) + r")\b[\s:\-]*" + _THE_WORD + _WORD, re.I)
_HINGLISH_RE = re.compile(_WORD + r"\s*(?:" + "|".join(HINGLISH_AFTER) + r")\b", re.I)
# "comment mein RECIPE likho": the word sits between the two halves.
_HINGLISH_MID_RE = re.compile(
    r"\b(?:comment|comments|dm)\s+(?:me|mein|mai|main|box\s+me|box\s+mein)\s+" + _WORD
    + r"\s*(?:likho|likhiye|likh\s+do|likh\s+dena|daalo|dalo|bhejo|bolo)\b",
    re.I,
)
# "comment for the link": any comment gets it, so there is no word to send.
_ANY_WORD_RE = re.compile(
    r"\b(" + _alt(COMMENT_VERBS + ["dm", "dm me"]) + r")\b\s+(?:below\s+|down\s+below\s+|now\s+)?"
    r"(?:for|to\s+get|to\s+receive)\s+(?:the\s+|a\s+|my\s+|free\s+|this\s+)*("
    + _alt([w for ws in PROMISES.values() for w in ws]) + r")\b",
    re.I,
)


def _clean(text) -> str:
    if isinstance(text, list):
        text = " ".join(str(t) for t in text)
    text = _EMOJI.sub(" ", str(text or ""))
    return re.sub(r"[ \t]+", " ", text)


def _snippet(text: str, start: int, end: int, pad: int = 70) -> str:
    a, b = max(0, start - pad), min(len(text), end + pad)
    out = re.sub(r"\s+", " ", text[a:b]).strip()
    return ("..." if a else "") + out + ("..." if b < len(text) else "")


def _is_marked(raw: str, word: str, text: str) -> bool:
    """Quoted, or in capitals inside ordinary mixed-case text."""
    if any(q in raw for q in _QUOTES):
        return True
    if len(word) >= 2 and word.isupper():
        letters = [ch for ch in text if ch.isalpha()]
        lower = sum(1 for ch in letters if ch.islower())
        return bool(letters) and lower / len(letters) > 0.3
    return False


def _promised_in(text: str) -> str:
    for token in re.findall(r"[a-z\-]+", text.lower()):
        if token in _PROMISE_OF:
            return _PROMISE_OF[token]
    return ""


def _judge(text: str, m: re.Match, word_group: int, kind: str) -> dict | None:
    word = m.group(word_group)
    low = word.lower()
    if low in STOP_TRIGGERS:
        return None
    raw = m.group(0)
    marked = _is_marked(raw, word, text) or bool(re.search(r"\bword\s+$", raw[: raw.lower().rfind(low)], re.I))
    names_promise = _PROMISE_OF.get(low, "")
    after = text[m.end(): m.end() + 140]
    before = text[max(0, m.start() - 140): m.start()]
    cue = _CUE_RE.search(after)

    if kind == "context":
        # "type RECIPE below": the comment section has to be named.
        if not _AFTER_COMMENT_CONTEXT.search(after):
            return None
    if kind == "comment" and _NOUN_BEFORE.search(text[max(0, m.start() - 12): m.start()]):
        return None
    # A lowercase, unquoted word only counts when it names the thing itself
    # ("comment link"); otherwise it is ordinary speech ("comment below").
    # Only as an instruction to the viewer: "I comment daily and I'll..." is not.
    said_by_someone = re.search(r"(?:^|\W)(?:i|we|they|he|she|people|everyone)\s+$",
                                text[max(0, m.start() - 12): m.start()], re.I)
    if not marked and not names_promise and not said_by_someone and not low.endswith("ly") \
            and _STRONG_RE.search(after):
        marked = True
    if not marked and not names_promise:
        return None

    if names_promise:
        promise = names_promise
    elif cue:
        promise = _promised_in(after[: cue.end() + 60]) or "other"
    elif kind == "dm":
        promise = _promised_in(after[:80]) or _promised_in(before[-60:]) or "other"
    else:
        return None
    return {
        "trigger": word.upper(),
        "promise": promise,
        "start": m.start(),
        "end": m.end(),
    }


def detect(texts: dict[str, object]) -> dict | None:
    """First hit across the reel's texts, or None. `texts` maps a source name
    (caption, transcript, on_screen) to its text."""
    for source, value in texts.items():
        text = _clean(value)
        if not text.strip():
            continue
        candidates = []
        for kind, regex, group in (
            ("comment", _COMMENT_RE, 2),
            ("context", _CONTEXT_RE, 2),
            ("dm", _DM_RE, 2),
            ("hinglish", _HINGLISH_RE, 1),
            ("hinglish", _HINGLISH_MID_RE, 1),
        ):
            for m in regex.finditer(text):
                hit = _judge(text, m, group, kind)
                if hit:
                    candidates.append(hit)
        for m in _ANY_WORD_RE.finditer(text):
            if m.group(1).lower().startswith("comment") and _NOUN_BEFORE.search(text[max(0, m.start() - 12): m.start()]):
                continue
            candidates.append(
                {"trigger": "ANY", "promise": _PROMISE_OF[m.group(2).lower()], "start": m.start(), "end": m.end()}
            )
        if candidates:
            # Prefer a real word to send, then something concrete over "other".
            candidates.sort(key=lambda h: (h["trigger"] == "ANY", h["promise"] == "other", h["start"]))
            hit = candidates[0]
            return {
                "trigger": hit["trigger"],
                "promise": hit["promise"],
                "source": source,
                "snippet": _snippet(text, hit["start"], hit["end"]),
            }
    return None


# --- Storage -----------------------------------------------------------------


def _texts_for(metadata_json: str) -> dict:
    try:
        meta = json.loads(metadata_json or "{}")
    except Exception:
        meta = {}
    return {
        "caption": meta.get("caption") or "",
        "on_screen": meta.get("relevant_visible_text") or meta.get("visible_text") or "",
        "transcript": meta.get("transcript") or "",
    }


def _is_post(url: str) -> bool:
    return "/p/" in (url or "")


def tag_reel(reel_id: str) -> dict | None:
    """Scan one reel and store (or clear) its tag. Never raises."""
    try:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT r.id, r.url, COALESCE(d.metadata_json, '{}') AS metadata_json "
                "FROM reels r LEFT JOIN reel_processing_diagnostics d ON d.reel_id = r.id "
                "WHERE r.id = ?",
                (reel_id,),
            ).fetchone()
            if not row:
                return None
            hit = None if _is_post(row["url"]) else detect(_texts_for(row["metadata_json"]))
            _store(connection, row["id"], hit)
        if hit:
            print(f"[comment-bait] {reel_id}: comment {hit['trigger']} for {hit['promise']}", flush=True)
        return hit
    except Exception as exc:
        print(f"[comment-bait] {reel_id} skipped: {exc!r}", flush=True)
        return None


def _store(connection, reel_id: str, hit: dict | None) -> None:
    if not hit:
        connection.execute("DELETE FROM comment_bait_reels WHERE reel_id = ?", (reel_id,))
        return
    connection.execute(
        "INSERT INTO comment_bait_reels (reel_id, trigger_word, promise, source, snippet, detector_version, tagged_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(reel_id) DO UPDATE SET trigger_word = excluded.trigger_word, promise = excluded.promise, "
        "source = excluded.source, snippet = excluded.snippet, detector_version = excluded.detector_version, "
        "tagged_at = CASE WHEN comment_bait_reels.trigger_word = excluded.trigger_word "
        "THEN comment_bait_reels.tagged_at ELSE excluded.tagged_at END",
        (reel_id, hit["trigger"], hit["promise"], hit["source"], hit["snippet"][:500], DETECTOR_VERSION,
         datetime.now().isoformat(timespec="seconds")),
    )


def backfill() -> dict:
    """Scan every saved reel. Text only, so it is quick and free."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT r.id, r.url, COALESCE(d.metadata_json, '{}') AS metadata_json "
            "FROM reels r LEFT JOIN reel_processing_diagnostics d ON d.reel_id = r.id"
        ).fetchall()
        scanned = tagged = 0
        for row in rows:
            scanned += 1
            try:
                hit = None if _is_post(row["url"]) else detect(_texts_for(row["metadata_json"]))
                _store(connection, row["id"], hit)
                tagged += 1 if hit else 0
            except Exception as exc:
                print(f"[comment-bait] backfill {row['id']} skipped: {exc!r}", flush=True)
    return {"scanned": scanned, "tagged": tagged, "version": DETECTOR_VERSION}


def backfill_once() -> dict | str:
    """Run the backfill on the first start of each DETECTOR_VERSION."""
    with get_connection() as connection:
        claimed = connection.execute(
            "INSERT OR IGNORE INTO maintenance_flags (flag, executed_at) VALUES (?, ?)",
            (f"comment_bait_backfill_{DETECTOR_VERSION}", datetime.now().isoformat(timespec="seconds")),
        ).rowcount == 1
    return backfill() if claimed else ""


def list_tagged() -> list[dict]:
    """One row per Instagram reel (the same reel saved by two people is one
    row). No user data: reel id, title, public reel URL and the tag only."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT c.reel_id, c.trigger_word, c.promise, c.source, c.snippet, c.tagged_at, r.url,
                   (SELECT item_name FROM reel_items i WHERE i.reel_id = c.reel_id AND item_name != ''
                    ORDER BY i.id LIMIT 1) AS title
            FROM comment_bait_reels c JOIN reels r ON r.id = c.reel_id
            ORDER BY c.tagged_at DESC, c.reel_id DESC
            """
        ).fetchall()
    out: dict[str, dict] = {}
    for row in rows:
        url = (row["url"] or "").split("?")[0].rstrip("/")
        if url in out:
            out[url]["saves"] += 1
            if not out[url]["title"] and row["title"]:
                out[url]["title"] = row["title"]
            continue
        out[url] = {
            "reel_id": row["reel_id"],
            "title": row["title"] or "",
            "url": url,
            "trigger": row["trigger_word"],
            "promise": row["promise"],
            "source": row["source"],
            "snippet": row["snippet"],
            "tagged_at": row["tagged_at"],
            "saves": 1,
        }
    return list(out.values())
