"""Search report: one AI read across the reels a search returned.

The user searches ("things to do in Hong Kong", "websites for vibe coding"),
taps Report, and gets what they would otherwise piece together by opening
every reel. The SHAPE of the report is not hard-coded: the writer works out
what the person is trying to do and assembles the report from three generic
blocks, so a city reads like a visitor's guide and a tools search reads like
a list of tools, without any per-topic rules in code.

  cards  one per named thing (place, website, app, product, title, dish...)
         with short facts and actions: Map for places, Open for a link the
         reel itself shows, Search otherwise
  steps  ordered instructions or a day-by-day plan
  tips   advice, warnings, takeaways

Two model calls, each doing one job (all numbers measured on the founder's
192-reel prod library against 16 hand-labelled queries, 84 must-use reels):

  1. JUDGE  defines what counts for this search ("looking_for", naming the
            near-misses to reject), then rules helps true/false on every
            candidate. Criteria-first took gpt-4.1-mini from 76/84 found with
            7 wrong to 83/84 with 3 wrong; folding judging into the writing
            call measured worse (82/84, 8 wrong): a model that wants to write
            stops being strict. gpt-4.1-nano judged worse AND slower.
  2. WRITER sees only the approved reels and streams, so cards appear as
            they are written instead of after a blank wait.

Candidates come from hybrid search topped up past its gate (recall_fill): the
gate is tuned for the results list, the judge filters here, and the top-up
took candidate recall from 77/84 to 84/84.

Admin-only while the founder tries it (plus REPORT_ACCOUNTS). Reports are
cached by query + the exact reel set, so reopening one never pays twice;
fresh generations are capped per user per day.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
from typing import Any, Iterator

from app.db.database import get_connection

REPORT_MODEL = "gpt-4.1-mini"
PROMPT_VERSION = "v16"
MIN_CANDIDATES = 24   # gate results topped up to this many for recall
MAX_CANDIDATES = 32   # hard ceiling, admitted results included
DAILY_GENERATIONS = 20
PARTIAL_EVERY = 0.35  # seconds between streamed partial renders

# Per-field character budgets. A fully processed reel measured ~450 tokens
# median / ~860 p90 across these fields (local library, 2026-10-05); the caps
# only bite on the long tail (rambling transcripts, essay captions).
FIELD_LIMITS = {
    "transcript": 1800,
    "caption": 700,
    "visible_text": 400,
    "visual_summary": 400,
    "item_summaries": 600,
    "visual_supporting_points": 400,
}

BLOCK_TYPES = ("cards", "steps", "tips")
CARD_KINDS = ("place", "activity", "stay", "dish", "website", "app", "product", "title", "person", "other")
PLACE_KINDS = ("place", "activity", "stay")

_DOMAIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?([a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\."
    r"(?:com|in|io|ai|app|dev|co|org|net|so|gg|me|xyz|tech|tools|studio|design|site|ly|to|fm|tv|ca|uk|us))\b",
    re.I,
)
_LABEL_RE = re.compile(r"\s*[\(\[]R\d+(?:\s*,\s*R\d+)*[\)\]]")
_STEP_NUM_RE = re.compile(r"(?:^|\s)(?:step\s*)?\d{1,2}[.):]\s+", re.I)


class ReportError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _norm(text: Any) -> str:
    return " ".join(str(text or "").split())


def _text(value: Any) -> str:
    """Model text with any leaked reel labels ("(R3)", "[R1, R4]") removed."""
    return _norm(_LABEL_RE.sub("", str(value or "")))


def _joined(value: Any, limit: int = 0) -> str:
    if isinstance(value, list):
        text = " | ".join(_norm(v) for v in value if _norm(v))
    else:
        text = _norm(value)
    return text[:limit] if limit else text


def search_report_enabled(user_id: str) -> bool:
    """Admins (settings.admin_emails) plus REPORT_ACCOUNTS, by email or id."""
    from app.config import settings

    if not user_id:
        return False
    if user_id.strip().lower() in settings.report_accounts:
        return True
    with get_connection() as conn:
        row = conn.execute(
            "SELECT lower(email) AS email FROM users WHERE id = ? LIMIT 1", (user_id,)
        ).fetchone()
    email = (row["email"] or "") if row else ""
    return bool(email) and (email in settings.admin_emails or email in settings.report_accounts)


# --------------------------------------------------------------- reels in ---

def _failed(doc: dict) -> bool:
    """Extraction crashed (quota, timeout) but caption/transcript often survived."""
    return any(_norm(n).lower() == "processing failed" for n in doc.get("item_names") or [])


def _reel_text(doc: dict) -> str:
    """Everything the reel itself says or shows: what links are checked against."""
    return " ".join(
        _joined(doc.get(f))
        for f in ("caption", "transcript", "visible_text", "item_summaries", "visual_summary", "hashtags")
    )


def _reel_block(label: str, doc: dict, picked: bool = False) -> str:
    lines = [f"[{label}]" + (" (USER PICKED)" if picked else "")]
    failed = _failed(doc)
    fields = [
        ("title", "" if failed else _joined(doc.get("item_names"))),
        ("subject", _joined(doc.get("main_subject"))),
        ("creator", _joined(doc.get("creator"))),
        ("places", _joined(doc.get("locations"))),
        ("mentions", _joined((doc.get("entities") or [])[:12])),
        ("summary", "" if failed else _joined(doc.get("item_summaries"), FIELD_LIMITS["item_summaries"])),
        ("on screen", _joined(doc.get("visible_text"), FIELD_LIMITS["visible_text"])),
        ("visual", _joined(doc.get("visual_summary"), FIELD_LIMITS["visual_summary"])),
        ("shown", _joined(doc.get("visual_supporting_points"), FIELD_LIMITS["visual_supporting_points"])),
        ("caption", _joined(doc.get("caption"), FIELD_LIMITS["caption"])),
        ("speech", _joined(doc.get("transcript"), FIELD_LIMITS["transcript"])),
    ]
    lines += [f"{name}: {text}" for name, text in fields if text]
    return "\n".join(lines)


# ---------------------------------------------------------------- prompts ---

def _judge_prompt(query: str, blocks: list[str]) -> str:
    return (
        f'The person searched their saved Instagram reels for: "{query}"\n\n'
        "Below are candidate reels from a loose search.\n\n"
        "First, in \"looking_for\", define in one or two sentences exactly what counts "
        "as an answer to this search and what does not (name the near-misses to "
        "reject). Then judge every reel against that definition. Count a reel only if "
        "the main thing the reel is about IS what was searched for (an example of it, "
        "or a direct answer to it). Sharing an ingredient, a word, a city, a tool, a "
        "flavour or a vibe is not enough: for \"sneakers\", a reel about socks or a "
        "shoe-cleaning spray does not count. When the search names a place to visit "
        "(a city, country or area, alone or as \"things to do in…\", \"…trip\"), the "
        "person is planning a trip there: anything a visitor would use AT that place "
        "counts (sights, activities, food, stays, getting around, tips); the same kind "
        "of thing somewhere else does not. Words like best, top, good, easy or cheap "
        "say what the person hopes for, not words the reel must use: a reel "
        "recommending or showing the thing counts. Judge each reel on its own.\n\n"
        'Return JSON: {"looking_for": "", "reels": [{"ref": "R1", "why": "<a few '
        'words>", "helps": true}]}\nList every reel.\n\n'
        "REELS:\n\n" + "\n\n".join(blocks)
    )


WRITER_SYSTEM = (
    "You turn a person's saved Instagram reels into a short, practical report. "
    "You only use what the reels contain, and you shape the report around what "
    "the person is trying to do."
)


def _writer_prompt(query: str, looking_for: str, blocks: list[str]) -> str:
    return (
        f'The person searched their saved Instagram reels for: "{query}"\n'
        + (f"What counts as an answer: {looking_for}\n" if looking_for else "")
        + "\nEvery reel below has already been checked and answers this search.\n\n"
        "Work out what the person is trying to do with this search, and build the "
        "report a friend would hand them for exactly that. Let the search decide the "
        "shape. For example: a city or country is a trip to plan, so write a guide a "
        "first-time visitor can act on (things to do, where to eat, where to stay, "
        "getting around, what to know before going); a search for tools, websites, "
        "apps or products wants each one listed with what it does and who it's for; a "
        "skill or how-to wants the technique and steps; ideas or inspiration want the "
        "options laid out side by side. These are examples, not a menu: pick whatever "
        "structure serves THIS search.\n\n"
        "Build the report from blocks, in the order the person needs them:\n"
        '- "cards": one card per individual named thing; never put several things in '
        "one card (a reel listing nine beaches gives nine cards). Merge the same thing "
        "across reels into one card that cites all of them. Something offered AT a "
        "place (a dish at a restaurant, a product at a shop) goes inside that place's "
        "card, not in a card of its own. Fields:\n"
        "  name: what it's called.\n"
        "  key: the ONE most useful concrete fact about it that the reels state, under "
        "6 words: a price, a time, a place, a number, or how to book (\"₹250 a plate\", "
        "\"Open till 2 AM\", \"Book on the app\"). It shows next to the name in a one-line list, so "
        "make it the reason to pick this one. Empty if the reels give no such fact; "
        "never a vague phrase like \"scenic views\".\n"
        "  kind: place (somewhere you can go: restaurant, cafe, stall, shop, attraction, "
        "beach), activity (a tour, show, class or experience at a place), stay, dish "
        "(a food or recipe), website, app, product, title (movie, show, book, song), "
        "person, other.\n"
        "  what: one short line on what it is and why it's worth it, from what the "
        "reels say. If a reel just names it, keep this minimal; never invent claims.\n"
        "  details: up to 3 short [label, value] facts the reels state (price, area, "
        "hours, how to book, key feature) that `what` doesn't already say. Values "
        "under 8 words. Leave it empty rather than pad it.\n"
        "  location: for place, activity and stay only, \"area, city\" including the "
        "city.\n"
        "  url: a web address ONLY if one is written in the reel, copied exactly; "
        "never guess one.\n"
        "  search: the few words someone would type into Google to find this exact "
        "thing (for a dish, its recipe).\n"
        '- "steps": a genuine ordered process or day-by-day plan the reels give, one '
        "step per item. When a reel teaches how to do something, write its actual "
        "steps; never squash a method into a one-line card. Two different methods "
        "are two steps blocks, each headed with what it makes or does.\n"
        '- "tips": advice, warnings, money and time savers, one per item.\n\n'
        "Use as few blocks as the content needs (a list of places can be one cards "
        "block; three different methods are three steps blocks). Never restate a "
        "card as a step or a tip. Give every block a label: one or two words for a "
        "tab that jumps to it (\"Food\", \"Stays\", \"Tools\", \"Steps\").\n\n"
        "Then pick the highlights: the 2 or 3 things the person should see first if "
        "they read nothing else, each one line under 16 words that names the pick "
        "and the fact that makes it worth it (\"Lake Louise: go before 8 AM or parking "
        "is full\"). Highlights may repeat facts from the cards; "
        "they are the summary at the top.\n\n"
        "Rules: use every reel. Each reel below must appear in at least one card or "
        "item, even one that only names things: a reel listing nine places gives nine "
        "cards with an empty key. Every card and item cites the reel(s) it came from in "
        "refs, like [\"R3\"]; never write reel labels inside the text. Never state "
        "anything the reels don't say. No filler or generic advice (\"try it for a "
        "complete experience\"). Never repeat a fact. Speech-to-text can be garbled "
        "Hindi/Hinglish: use only what is clear. Write in plain, simple English and "
        "keep it tight.\n\n"
        "Return JSON:\n"
        '{"title": "<short title for this report>", '
        '"highlights": [{"text": "", "refs": ["R2"]}], '
        '"blocks": [{"type": "cards", "label": "<1-2 words>", "heading": "<heading>", '
        '"items": [{"name": "", "key": "", "kind": "", "what": "", '
        '"details": [["Price", "₹250 a plate"]], "location": "", "url": "", "search": "", '
        '"refs": ["R2"]}]}, '
        '{"type": "steps", "label": "", "heading": "<heading>", "items": [{"text": "", "refs": ["R1"]}]}, '
        '{"type": "tips", "label": "", "heading": "<heading>", "items": [{"text": "", "refs": ["R4"]}]}], '
        '"gaps": "<one sentence on what this person would want that these reels do '
        'not cover, or empty>"}\n\n'
        "REELS:\n\n" + "\n\n".join(blocks)
    )


# ----------------------------------------------------------- model calls ---

def _client():
    from api_config import get_openai_client

    return get_openai_client()


def _usage(usage: Any) -> dict:
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
    }


def _judge(query: str, labels: dict[str, str], docs: dict, model: str) -> tuple[str, dict[str, str], set[str], dict]:
    """→ (looking_for, {reel_id: why} for rejected reels, helpful ids, usage)."""
    blocks = [_reel_block(label, docs[rid]) for label, rid in labels.items()]
    resp = _client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": _judge_prompt(query, blocks)}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = json.loads(resp.choices[0].message.content or "{}")
    helpful, rejected = set(), {}
    for verdict in raw.get("reels") or []:
        if not isinstance(verdict, dict):
            continue
        rid = labels.get(_norm(verdict.get("ref")).upper())
        if not rid:
            continue
        if verdict.get("helps") is True:
            helpful.add(rid)
        else:
            rejected[rid] = _text(verdict.get("why"))
    return _text(raw.get("looking_for")), rejected, helpful, _usage(resp.usage)


def _write_stream(query: str, looking_for: str, labels: dict[str, str], docs: dict, model: str) -> Iterator[tuple[str, dict | None]]:
    """Yields (text so far, None) while streaming, then (full text, usage) once."""
    blocks = [_reel_block(label, docs[rid]) for label, rid in labels.items()]
    stream = _client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": WRITER_SYSTEM},
            {"role": "user", "content": _writer_prompt(query, looking_for, blocks)},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
        stream=True,
        stream_options={"include_usage": True},
    )
    text, usage = "", {}
    for chunk in stream:
        if getattr(chunk, "usage", None):
            usage = _usage(chunk.usage)
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            text += chunk.choices[0].delta.content
            yield text, None
    yield text, usage


def _partial_json(text: str) -> dict | None:
    """Parse a JSON object that is still being written, cut back to the last
    completed {...} and closed off. Only finished cards/items ever render, so
    nothing half-written (a truncated name or link) reaches the screen."""
    stack: list[str] = []
    in_str = esc = False
    best: tuple[int, str] | None = None
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
            if ch == "}" and stack:
                best = (i + 1, "".join(reversed(stack)))
    if best is None:
        return None
    try:
        value = json.loads(text[: best[0]] + best[1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


# ------------------------------------------------------------- cleaning ---

def _domain(url: str) -> str:
    match = _DOMAIN_RE.search(url or "")
    return match.group(1).lower() if match else ""


def _verified_url(url: str, source_text: str) -> str:
    """A link survives only if the cited reels actually show that domain.
    The model is told never to guess; this makes it impossible."""
    domain = _domain(url)
    if not domain:
        return ""
    shown = {d.lower() for d in _DOMAIN_RE.findall(source_text)}
    if domain not in shown:
        return ""
    url = _norm(url)
    return url if url.lower().startswith(("http://", "https://")) else "https://" + url


def _reel_city(reel_ids: list[str], docs: dict) -> str:
    """The cited reels' own location tag ("Varanasi"), so a Map search for a
    stall the model only placed by neighbourhood still lands in the right city."""
    for rid in reel_ids:
        places = [p for p in (docs.get(rid, {}).get("locations") or []) if _norm(p)]
        if places:
            return _norm(places[0])
    return ""


def _actions(card: dict, url: str, search: str) -> list[dict]:
    actions = []
    is_place = card["kind"] in PLACE_KINDS and (card["kind"] != "activity" or card["location"])
    if is_place:
        place = ", ".join(x for x in (card["name"], card["location"]) if x)
        actions.append({
            "label": "Map",
            "href": "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(place),
        })
    if url:
        actions.append({"label": "Open", "href": url})
    if not url and not is_place:
        actions.append({
            "label": "Search",
            "href": "https://www.google.com/search?q=" + urllib.parse.quote(search or card["name"]),
        })
    return actions


def _block_items(block: dict) -> list:
    """A block's list, whatever the writer called it ("items", "cards"…)."""
    if isinstance(block.get("items"), list):
        return block["items"]
    return next((v for v in block.values() if isinstance(v, list) and v and isinstance(v[0], dict)), [])


def _block_type(block: dict) -> str:
    """The writer's JSON wobbles between runs ("card" vs "cards", a missing
    type): measured once wiping every card from an "ai tools" report. Read the
    type loosely and fall back to what the items look like."""
    kind = _norm(block.get("type")).lower()
    for name in BLOCK_TYPES:
        if kind in (name, name.rstrip("s")):
            return name
    items = [i for i in _block_items(block) if isinstance(i, dict)]
    if items and any(i.get("name") or i.get("title") for i in items):
        return "cards"
    return "tips" if items else ""


def _clean_blocks(raw: dict, labels: dict[str, str], helpful: set[str], docs: dict) -> list[dict]:
    """Keep only items citing an approved reel; build verified card actions;
    merge a thing carded twice into one card citing both reels."""
    def refs_of(value: Any) -> list[str]:
        if isinstance(value, (str, int)):
            value = re.findall(r"\d+", str(value))
        out: list[str] = []
        for ref in value or []:
            ref = _norm(ref).upper()
            rid = labels.get(ref if ref.startswith("R") else "R" + ref)
            if rid in helpful and rid not in out:
                out.append(rid)
        return out

    blocks, seen_cards = [], {}
    for block in raw.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        btype = _block_type(block)
        if not btype:
            continue
        items = []
        for item in _block_items(block):
            if not isinstance(item, dict):
                continue
            refs = refs_of(next((item.get(k) for k in ("refs", "ref", "reels", "sources", "source", "citations") if item.get(k)), None))
            if not refs:
                continue
            if btype != "cards":
                text = _text(item.get("text") or item.get("tip") or item.get("step"))
                # One item holding "1. … 2. … 3. …" is several steps.
                parts = [p.strip() for p in _STEP_NUM_RE.split(text) if p.strip()]
                for part in (parts if len(parts) > 1 else [_STEP_NUM_RE.sub("", text, count=1).strip() or text]):
                    items.append({"text": part, "reel_ids": refs})
                continue
            name = _text(item.get("name") or item.get("title"))
            if not name:
                continue
            twin = seen_cards.get(name.lower())
            if twin is not None:
                twin["reel_ids"] += [rid for rid in refs if rid not in twin["reel_ids"]]
                continue
            kind = _norm(item.get("kind")).lower()
            kind = kind if kind in CARD_KINDS else "other"
            what = _text(item.get("what"))
            location = ""
            if kind in PLACE_KINDS:
                # "Sidemen" at "Sidemen, Bali" shows as just "Bali".
                parts = [p.strip() for p in _norm(item.get("location")).split(",") if p.strip()]
                parts = [p for p in parts if p.lower() != name.lower()]
                city = _reel_city(refs, docs)
                if city and city.lower() not in " ".join(parts).lower():
                    parts.append(city)
                location = ", ".join(parts)
            # A fact earns its row only if it adds something: not already in
            # the one-liner, and not the location line said again.
            said = _words(what) | _words(location)
            details = []
            for pair in item.get("details") or []:
                if isinstance(pair, (list, tuple)) and len(pair) == 2 and _text(pair[0]) and _text(pair[1]):
                    value = _words(_text(pair[1]))
                    if value and len(value & said) / len(value) < 0.8:
                        details.append([_text(pair[0]), _text(pair[1])])
            details = details[:3]
            # The one fact shown beside the name in the compact row. A model
            # key that only restates the name is no fact; then the first
            # stated detail stands in.
            key = _text(item.get("key"))[:48]
            if key and _words(key) <= _words(name):
                key = ""
            if not key and details:
                key = details[0][1]
            card = {
                "name": name,
                "kind": kind,
                "key": key,
                "what": what,
                "details": details,
                "location": location,
                "reel_ids": refs,
                # No fact at all (measured: 46% of cards) - the UI folds
                # these into one "Also mentioned" line instead of a full row.
                "thin": not key and not details,
            }
            source = " ".join(_reel_text(docs[rid]) for rid in refs if rid in docs)
            card["actions"] = _actions(card, _verified_url(_norm(item.get("url")), source), _text(item.get("search")))
            seen_cards[name.lower()] = card
            items.append(card)
        if btype == "steps" and len(items) == 1:
            # A one-step "method" is a tip, not a process to expand.
            btype = "tips"
        if items:
            heading = _text(block.get("heading") or block.get("title"))
            if btype == "cards":
                # Cards that carry a fact first; stable, so the writer's order
                # holds within each group.
                items.sort(key=lambda c: c["thin"])
            blocks.append({
                "type": btype,
                "label": _label(_text(block.get("label")), heading, btype),
                "heading": heading,
                "items": items,
            })
    return _drop_restated(blocks)


_LABEL_FILLER = frozenset(
    "top best must the a an of for in to and with your my practical recommended popular "
    "key quick essential guide ideas options how what where".split()
)


def _label(label: str, heading: str, btype: str) -> str:
    """One or two words for the section's jump tab."""
    if label and len(label) <= 18:
        return label
    words = label.split()[:2]
    while words and words[-1].lower() in _LABEL_FILLER:
        words.pop()
    if words:
        return " ".join(words)[:18]
    if btype != "cards":
        return "Steps" if btype == "steps" else "Tips"
    useful = [w for w in re.findall(r"[A-Za-z0-9&'-]+", heading) if w.lower() not in _LABEL_FILLER]
    return (useful[0][:1].upper() + useful[0][1:]) if useful else "Picks"


def _clean_highlights(raw: dict, labels: dict[str, str], helpful: set[str]) -> list[dict]:
    """The Quick take: up to 3 lines, each citing an approved reel."""
    out = []
    for item in raw.get("highlights") or []:
        text = _text(item.get("text") if isinstance(item, dict) else item)
        refs_value = item.get("refs") if isinstance(item, dict) else None
        if isinstance(refs_value, (str, int)):
            refs_value = re.findall(r"\d+", str(refs_value))
        refs = []
        for ref in refs_value or []:
            ref = _norm(ref).upper()
            rid = labels.get(ref if ref.startswith("R") else "R" + ref)
            if rid in helpful and rid not in refs:
                refs.append(rid)
        if text and refs:
            out.append({"text": text, "reel_ids": refs})
        if len(out) == 3:
            break
    return out


_STOP = frozenset(
    "a an the and or of to in on at for with by from as is are be it its this that these "
    "your you their they them can will just also very more most into over about than then "
    "use using try get make so if not no".split()
)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9₹]+", text.lower()) if w not in _STOP and len(w) > 1}


def _card_words(card: dict) -> set[str]:
    return _words(" ".join([card["name"], card["what"]] + [v for pair in card["details"] for v in pair]))


def _drop_restated(blocks: list[dict]) -> list[dict]:
    """Drop what only restates a card from the same reels. The writer is told
    not to and measured ignoring it twice (a Bali report repeated every card as
    a "step" and again as a "tip"; a Varanasi report re-carded every dish
    right after the restaurant card that already named it), so it is enforced
    here.
      dish/product card whose name already appears on a PLACE card from the
          same reel (the restaurant or shop it's sold at): folded into that
          card, keeping any fact the place card lacks ("Fish fry: ₹500/kg")
      step/tip whose words mostly already sit on cards citing its reels"""
    places = [c for b in blocks if b["type"] == "cards" for c in b["items"] if c["kind"] in PLACE_KINDS]

    def home_of(card: dict) -> dict | None:
        name = _words(card["name"])
        for place in places:
            if place is not card and set(place["reel_ids"]) & set(card["reel_ids"]):
                if name and len(name & _card_words(place)) / len(name) >= 0.6:
                    return place
        return None

    folded = set()
    for block in blocks:
        if block["type"] != "cards":
            continue
        for card in block["items"]:
            if card["kind"] not in ("dish", "product"):
                continue
            place = home_of(card)
            if place is None:
                continue
            known = _card_words(place)
            for label, value in card["details"]:
                if len(place["details"]) < 4 and not _words(value) <= known:
                    place["details"].append([card["name"], value])
            folded.add(id(card))

    card_words: dict[str, set[str]] = {}
    for block in blocks:
        if block["type"] == "cards":
            for card in block["items"]:
                if id(card) not in folded:
                    for rid in card["reel_ids"]:
                        card_words.setdefault(rid, set()).update(_card_words(card))

    def restated(item: dict) -> bool:
        words = _words(item["text"])
        covered = set().union(*(card_words.get(rid, set()) for rid in item["reel_ids"]))
        return bool(words) and len(words & covered) / len(words) >= 0.6

    kept = []
    for block in blocks:
        if block["type"] == "cards":
            items = [c for c in block["items"] if id(c) not in folded]
        else:
            items = [i for i in block["items"] if not restated(i)]
        if items:
            kept.append({**block, "items": items})
    return kept


def _number(blocks: list[dict], used: list[str], highlights: list[dict] | None = None) -> list[dict]:
    """Reel numbers follow the judge's approved list (search-rank order), so
    they're fixed before writing starts and never shift while streaming."""
    number = {rid: i + 1 for i, rid in enumerate(used)}
    items = [item for block in blocks for item in block["items"]] + list(highlights or [])
    for item in items:
        item["refs"] = sorted(number[rid] for rid in item["reel_ids"] if rid in number)
    return blocks


def _reel_payload(doc: dict, why: str = "") -> dict:
    from app.services.deep_search import _result_payload

    item = _result_payload(doc, 0, [])
    if _failed(doc):
        item["item_names"] = [_norm(doc.get("main_subject")) or "Saved reel"]
    if why:
        item["why"] = why
    return item


def _reel_thumb(doc: dict) -> dict:
    """Just enough for a thumbnail in the live progress strip."""
    names = [_norm(doc.get("main_subject")) or "Saved reel"] if _failed(doc) else (doc.get("item_names") or [])[:1]
    return {"reel_id": doc["reel_id"], "url": doc.get("url", ""), "item_names": names, "media": doc.get("media", {})}


def _payload(report: dict, docs: dict, query: str, excluded: list[str], cached: bool, usage: dict) -> dict:
    used = [rid for rid in report["used"] if rid in docs]
    highlights = report.get("highlights") or []
    blocks = _number(report["blocks"], used, highlights)
    has_content = bool(blocks)
    skipped = [
        _reel_payload(docs[rid], report["skipped_why"].get(rid) or "Not about this search")
        for rid in report["candidates"] if rid not in used and rid in docs
    ] + [_reel_payload(docs[rid], "Removed by you") for rid in excluded if rid in docs]
    return {
        "status": "ok" if has_content else "no_match",
        "query": query,
        "title": (report["title"] if has_content else "") or query,
        "looking_for": report.get("looking_for", ""),
        # With nothing usable, the model's intro/gaps describe the rejected
        # reels ("potentially useful for…") and contradict the empty state.
        "intro": report["intro"] if has_content else "",
        "highlights": highlights if has_content else [],
        "gaps": report["gaps"] if has_content else "",
        "blocks": blocks,
        "used": [_reel_payload(docs[rid]) for rid in used] if has_content else [],
        "skipped": ([] if has_content else [_reel_payload(docs[rid]) for rid in used]) + skipped,
        "cached": cached,
        "usage": usage,
    }


# ------------------------------------------------------------------ entry ---

def _candidates(user_id: str, query: str, docs: dict, include: set[str], exclude: set[str]) -> list[str]:
    from app.services.deep_search import search_user_documents
    from app.services.deep_search_hybrid import search_documents_hybrid

    try:
        results = search_documents_hybrid(
            list(docs.values()), query, limit=MAX_CANDIDATES, recall_fill=MIN_CANDIDATES + len(exclude)
        )
    except Exception:
        results = None
    if results is None:
        # No embeddings / OpenAI down: fall back to the app's own search path.
        results = search_user_documents(user_id, query, limit=MAX_CANDIDATES).get("results") or []
    candidate_ids: list[str] = []
    for result in results:
        rid = result.get("reel_id")
        if rid in docs and rid not in exclude and rid not in candidate_ids:
            candidate_ids.append(rid)
    candidate_ids = candidate_ids[:MAX_CANDIDATES]
    for rid in include:
        if rid not in candidate_ids:
            candidate_ids.append(rid)
    return candidate_ids


def _cache_key(user_id: str, query: str, candidate_ids: list[str], include: set[str], model: str) -> str:
    raw = json.dumps(
        [PROMPT_VERSION, model, user_id, query.lower(), candidate_ids, sorted(include)],
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


def _save(user_id: str, query: str, key: str, report: dict, model: str, usage: dict) -> None:
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
            (user_id, query, key, json.dumps(report["candidates"]), json.dumps(report), model,
             usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), _now()),
        )


def report_events(
    user_id: str,
    query: str,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    model: str = REPORT_MODEL,
) -> Iterator[dict]:
    """The report as a stream of events, for the live UI:
      {"event": "judging", "candidates": n}
      {"event": "judged", "looking_for", "used": [reels], "skipped_count"}
      {"event": "partial", "report": {...}}   (repeated while writing)
      {"event": "done", "report": {...}}      (always last on success)
    Raises ReportError for user-facing failures."""
    from app.services.deep_search import load_deep_search_documents

    query = _norm(query)[:200]
    if not query:
        raise ReportError("Search for something first", status=400)

    docs = {d["reel_id"]: d for d in load_deep_search_documents(user_id) if d.get("reel_id")}
    include_set = {rid for rid in (include or []) if rid in docs}
    exclude_set = {rid for rid in (exclude or []) if rid in docs} - include_set
    candidates = _candidates(user_id, query, docs, include_set, exclude_set)
    excluded = [rid for rid in (exclude or []) if rid in exclude_set]

    if not candidates:
        yield {"event": "done", "report": {
            "status": "empty", "query": query, "title": query, "looking_for": "", "intro": "", "highlights": [],
            "gaps": "", "blocks": [], "used": [], "skipped": [], "cached": False, "usage": {}}}
        return

    key = _cache_key(user_id, query, candidates, include_set, model)
    with get_connection() as conn:
        row = conn.execute("SELECT report_json FROM search_reports WHERE cache_key = ? LIMIT 1", (key,)).fetchone()
    if row:
        yield {"event": "done", "report": _payload(json.loads(row["report_json"]), docs, query, excluded, True, {})}
        return

    if _generations_today(user_id) >= DAILY_GENERATIONS:
        raise ReportError(f"You've made {DAILY_GENERATIONS} reports today. More tomorrow.", status=429)

    started = time.time()
    yield {"event": "judging", "candidates": len(candidates), "reels": [_reel_thumb(docs[rid]) for rid in candidates]}
    labels = {f"R{i + 1}": rid for i, rid in enumerate(candidates)}
    try:
        looking_for, rejected, helpful, judge_usage = _judge(query, labels, docs, model)
    except Exception as exc:
        raise ReportError("Couldn't read your reels right now. Try again in a bit.") from exc
    helpful |= include_set
    used = [rid for rid in candidates if rid in helpful]
    report = {
        "candidates": candidates, "used": used, "looking_for": looking_for,
        "skipped_why": {rid: why for rid, why in rejected.items() if rid not in helpful},
        "title": "", "intro": "", "highlights": [], "gaps": "", "blocks": [],
    }
    yield {"event": "judged", "looking_for": looking_for, "used": [_reel_thumb(docs[rid]) for rid in used],
           "skipped_count": len(candidates) - len(used)}

    usage = dict(judge_usage)
    if used:
        write_labels = {f"R{i + 1}": rid for i, rid in enumerate(used)}
        last_emit, last_len, raw = 0.0, 0, {}
        try:
            for text, write_usage in _write_stream(query, looking_for, write_labels, docs, model):
                if write_usage is not None:
                    raw = json.loads(text or "{}")
                    for k in ("prompt_tokens", "completion_tokens"):
                        usage[k] = usage.get(k, 0) + write_usage.get(k, 0)
                    break
                if time.time() - last_emit < PARTIAL_EVERY or len(text) - last_len < 40:
                    continue
                partial = _partial_json(text)
                if not partial:
                    continue
                blocks = _clean_blocks(partial, write_labels, set(used), docs)
                highlights = _clean_highlights(partial, write_labels, set(used))
                if blocks or highlights:
                    last_emit, last_len = time.time(), len(text)
                    yield {"event": "partial", "report": {
                        "title": _text(partial.get("title")), "intro": _text(partial.get("intro")),
                        "highlights": highlights, "blocks": _number(blocks, used, highlights)}}
        except Exception:
            raw = {}
        blocks = _clean_blocks(raw, write_labels, set(used), docs)
        if not blocks:
            # Approved reels but nothing usable came back (broken JSON or an
            # unreadable shape): one plain retry before failing the report.
            try:
                for text, write_usage in _write_stream(query, looking_for, write_labels, docs, model):
                    if write_usage is not None:
                        raw = json.loads(text or "{}")
                        for k in ("prompt_tokens", "completion_tokens"):
                            usage[k] = usage.get(k, 0) + write_usage.get(k, 0)
            except Exception as exc:
                raise ReportError("Couldn't write the report right now. Try again in a bit.") from exc
            blocks = _clean_blocks(raw, write_labels, set(used), docs)
            if not blocks:
                raise ReportError("Couldn't write the report right now. Try again in a bit.")
        report.update({
            "title": _text(raw.get("title")),
            "intro": _text(raw.get("intro")),
            "highlights": _clean_highlights(raw, write_labels, set(used)),
            "gaps": _text(raw.get("gaps")),
            "blocks": blocks,
        })
    usage["seconds"] = round(time.time() - started, 1)
    _save(user_id, query, key, report, model, usage)
    yield {"event": "done", "report": _payload(report, docs, query, excluded, False, usage)}


# ------------------------------------------------------------- usage ---

# What the report screen reports back: which parts get used, so the next
# layout change rests on behaviour, not on one person's reaction. Names and
# short labels only (an action's label, a card's kind), never card text.
REPORT_EVENTS = frozenset({
    "view", "expand", "action", "watch", "jump", "more", "steps",
    "expand_all", "share", "edit", "update",
})
DAILY_EVENTS = 400


def record_report_event(user_id: str, event: str, detail: str = "", query: str = "") -> bool:
    if event not in REPORT_EVENTS or not user_id:
        return False
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM report_events WHERE user_id = ? AND created_at >= ?",
            (user_id, time.strftime("%Y-%m-%d") + " 00:00:00"),
        ).fetchone()
        if int(row["n"] or 0) >= DAILY_EVENTS:
            return False
        conn.execute(
            "INSERT INTO report_events (user_id, event, detail, query, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, event, _norm(detail)[:40], _norm(query)[:120], _now()),
        )
    return True


def report_event_summary(days: int = 30) -> dict:
    since = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - max(1, days) * 86400))
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT event, detail, COUNT(*) AS n, COUNT(DISTINCT user_id) AS users
            FROM report_events WHERE created_at >= ?
            GROUP BY event, detail ORDER BY n DESC
            """,
            (since,),
        ).fetchall()
    return {"days": days, "events": [dict(r) for r in rows]}


def build_search_report(
    user_id: str,
    query: str,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    model: str = REPORT_MODEL,
) -> dict:
    """Non-streaming: the finished report (what the "done" event carries)."""
    for event in report_events(user_id, query, include, exclude, model):
        if event["event"] == "done":
            return event["report"]
    raise ReportError("Couldn't write the report right now. Try again in a bit.")
