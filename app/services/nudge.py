"""The nudge state machine. One place decides what the bot is allowed to say.

Implements NUDGE_RULEBOOK.md. Read that first: it carries the reasoning, this
carries the mechanism.

The split the rulebook insists on, and the reason this module exists: code
decides *whether* and *which*, so the decision is replayable and countable. A
model may later rewrite the wording, but never the eligibility, never the
timing, and never whether the 24 hour window is open.

Everything here fails closed. An account that is not explicitly allowed gets
silence, and any error is logged rather than raised, because this runs inside
reel ingest and inside the job worker and must never cost someone their reel.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.db.database import get_connection
from app.services.instagram_send import (
    MAX_BUTTON_TITLE_CHARS,
    send_button_template,
    send_quick_replies,
    send_sender_action,
    send_text,
)

# Reel counts at which the funnel changes shape. From the rulebook.
HOME_SCREEN_AT = 5
HEADS_UP_AT = 17
LOCK_AT = 20
LAST_CALL_AFTER_HOURS = 23
# Meta shuts the window at 24h. Past this there is no point attempting a send.
WINDOW_HOURS = 24

# Highest precedence first. When several messages are eligible at the same
# moment, one wins and the rest are dropped rather than queued.
PRECEDENCE = [
    "m10_month_cap",
    "m21_delete_ack",
    "m6_lock",
    "m5_heads_up",
    "m4_home_screen",
    "m7_past_lock",
    "m2_first_library",
    "m1_first_ack",
    "m17_already_saved",
    "m9_could_not_read",
    "m15_photo_post",
    "m16_unreadable_share",
    "m11_how_to_save",
    "m12_what_it_does",
    "m13_is_it_free",
    "m8_recovery",
    "m3_quiet_nudge",
]

ONCE_EVER = {"m1_first_ack", "m2_first_library", "m4_home_screen", "m5_heads_up", "m6_lock"}

# Judged against the last time the SAME message went out, not against the
# last DM of any kind. The failure reply usually follows the first-reel ack by
# a minute or two, so the shared cooldown would swallow exactly the case it
# exists for: "give me a few minutes", then silence. Measuring it against
# itself still stops ten bad links producing ten replies. The answers to a
# direct question are here for the same reason: two questions in a row are
# two questions, and the second must not be eaten by the first answer.
SELF_COOLDOWN = {
    "m9_could_not_read",
    "m10_month_cap",
    "m11_how_to_save",
    "m12_what_it_does",
    "m13_is_it_free",
    "m15_photo_post",
    "m16_unreadable_share",
    "m17_already_saved",
    "m21_delete_ack",
}

# Messages that are nothing without the person's own link. With no link to
# give (PUBLIC_BASE_URL unset) these are skipped rather than sent empty.
NEEDS_LINK = {"m2_first_library", "m4_home_screen", "m6_lock", "m7_past_lock", "m8_recovery"}

# How long the typing dots show before a message, in seconds. Short for the
# instant acknowledgement so it still reads as instant, longest for the first
# library message.
TYPING_SECONDS = {"m1_first_ack": 1.2, "m2_first_library": 2.0}
TYPING_SECONDS_DEFAULT = 1.5
# "Seen" and the dots are decoration. Meta's send endpoint can hang for its
# full timeout, and this runs inside the reel worker too, so they get a short
# one of their own and a failure simply skips the pause.
SENDER_ACTION_TIMEOUT_SECONDS = 6

# Chips offered under an answer to a typed question, so a wrong guess about
# what they meant costs one tap. Titles are cut at 20 characters by Instagram.
QUESTION_CHIPS = [
    {"title": "How do I save a reel", "payload": "ICE_HOW"},
    {"title": "What does it do", "payload": "ICE_WHAT"},
    {"title": "Is it free", "payload": "ICE_FREE"},
]
HOW_TO_SHARE_CHIP = [{"title": "How to share a reel", "payload": "ICE_HOW"}]

# What woke us, to the answer it gets. The typed_ variants are the same
# answers with the chips above attached, since a typed question was guessed at.
ANSWER_FOR = {
    "ask_how": "m11_how_to_save",
    "typed_how": "m11_how_to_save",
    "ask_what": "m12_what_it_does",
    "typed_what": "m12_what_it_does",
    "ask_free": "m13_is_it_free",
    "typed_free": "m13_is_it_free",
}

# The monthly cap counts only reels received after this flag was first
# stamped, so nobody's existing library uses up their month on the day the
# cap arrives.
MONTH_CAP_FLAG = "monthly_reel_cap_live"
# The month turns over at midnight in India, where the users are.
_IST = timezone(timedelta(hours=5, minutes=30))

# There is deliberately no cap on quiet nudges. The 24 hour window already
# enforces one: a nudge that goes unanswered is followed by the window
# closing, after which the person cannot be messaged at all. So at most one
# nudge per dormancy can ever be sent, and a counter for it would be a
# variable that is only ever 0 or 1.


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat((value or "").strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def log_event(kind: str, sender_id: str, outcome: str, detail: str = "") -> None:
    """Write to the same table the health view reads, so every decision is
    visible from outside without database access."""
    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO instagram_webhook_events
                    (received_at, kind, sender_id, sender_username, link_code, outcome, detail)
                VALUES (?, ?, ?, '', '', ?, ?)
                """,
                (_iso(_now()), kind, sender_id, outcome, (detail or "")[:500]),
            )
    except Exception:
        pass


def record_inbound(instagram_user_id: str) -> None:
    """Stamp when someone messaged us. The whole reply window hangs off this."""
    try:
        with get_connection() as connection:
            connection.execute(
                "UPDATE users SET last_inbound_at = ? WHERE instagram_user_id = ?",
                (_iso(_now()), (instagram_user_id or "").strip()),
            )
    except Exception:
        pass


def sender_allowed(instagram_user_id: str, instagram_username: str = "") -> bool:
    """Is this Instagram sender named in the test allowlist, by id or handle?

    Used before an account exists, which is why it takes raw identifiers
    rather than a user row.
    """
    allow = settings.guest_test_senders
    if not allow:
        return False
    if (instagram_user_id or "").strip().lower() in allow:
        return True
    handle = (instagram_username or "").strip().lower().lstrip("@")
    return bool(handle) and handle in allow


def replies_allowed(user: dict[str, Any]) -> bool:
    """Closed by default. Being named is the only way to be messaged.

    No admin bypass: that existed once as a testing convenience and promptly
    sent a DM to an account nobody had listed.
    """
    if settings.dm_reply_for_everyone:
        return True
    if (user.get("id") or "").strip().lower() in settings.dm_reply_accounts:
        return True
    handle = (user.get("instagram_username") or "").strip().lower().lstrip("@")
    igsid = (user.get("instagram_user_id") or "").strip().lower()
    if handle in settings.guest_test_senders or igsid in settings.guest_test_senders:
        return True
    email = (user.get("email") or "").strip().lower()
    return bool(email) and email in settings.dm_reply_accounts


def is_locked(user_id: str) -> bool:
    """Has this account hit the wall without signing in?

    The wall has to actually hold, not just be announced. Every reel past it
    costs real money to process, and a guest who never signs in could
    otherwise sit at forty reels on the house. The reel is still kept: it is
    buffered and drains the moment they sign in.
    """
    if not settings.guest_lock_enabled:
        return False
    try:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT COALESCE(google_sub, '') AS g, "
                "(SELECT COUNT(*) FROM reels WHERE user_id = users.id) AS n "
                "FROM users WHERE id = ? LIMIT 1",
                (user_id,),
            ).fetchone()
        if not row:
            return False
        if (row["g"] or "").strip():
            return False
        return int(row["n"] or 0) >= LOCK_AT
    except Exception:
        return False


def _month_start() -> datetime:
    return datetime.now(_IST).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def over_monthly_cap(user_id: str) -> bool:
    """Has this account already saved its reels for the month?

    Applies to everyone, signed in or not: every reel costs money to read.
    Counted from the reels table, against whichever is later of the 1st of
    the month and the moment the cap went live.
    """
    cap = settings.monthly_reel_cap
    if cap <= 0:
        return False
    try:
        # Reels are stamped in naive server-local time, so compare in that.
        month_start = _month_start().astimezone().replace(tzinfo=None).isoformat(timespec="seconds")
        with get_connection() as connection:
            row = connection.execute(
                "SELECT executed_at FROM maintenance_flags WHERE flag = ? LIMIT 1", (MONTH_CAP_FLAG,)
            ).fetchone()
            if row:
                live_since = row["executed_at"]
            else:
                live_since = datetime.now().isoformat(timespec="seconds")
                connection.execute(
                    "INSERT OR IGNORE INTO maintenance_flags (flag, executed_at) VALUES (?, ?)",
                    (MONTH_CAP_FLAG, live_since),
                )
            n = connection.execute(
                "SELECT COUNT(*) AS n FROM reels WHERE user_id = ? AND received_at >= ?",
                (user_id, max(month_start, live_since)),
            ).fetchone()["n"]
        return int(n or 0) >= cap
    except Exception:
        return False


def load_state(user_id: str) -> dict[str, Any] | None:
    """Everything a decision needs, in one read."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, email, google_sub, instagram_user_id, instagram_username, "
            "library_token, last_dm_at, last_inbound_at "
            "FROM users WHERE id = ? LIMIT 1",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        reel_count = connection.execute(
            "SELECT COUNT(*) AS n FROM reels WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]
        last_sent = {
            r["message_key"]: r["last_at"]
            for r in connection.execute(
                "SELECT message_key, MAX(sent_at) AS last_at FROM nudge_log "
                "WHERE user_id = ? GROUP BY message_key",
                (user_id,),
            )
        }
        sent = set(last_sent)
        completed_count = connection.execute(
            "SELECT COUNT(*) AS n FROM reels WHERE user_id = ? AND status = 'completed'", (user_id,)
        ).fetchone()["n"]
        # Reels waiting behind the sign-in wall live in the webhook log.
        held_count = connection.execute(
            "SELECT COUNT(DISTINCT detail) AS n FROM instagram_webhook_events "
            "WHERE kind = 'reel' AND outcome = 'buffered' AND sender_id = ? AND sender_id != ''",
            ((row["instagram_user_id"] or "").strip(),),
        ).fetchone()["n"]
    user = dict(row)
    user["reel_count"] = int(reel_count or 0)
    user["completed_count"] = int(completed_count or 0)
    user["held_count"] = int(held_count or 0)
    user["already_sent"] = sent
    user["last_sent_at"] = last_sent
    user["signed_in"] = bool((row["google_sub"] or "").strip())
    return user


def window_open(user: dict[str, Any]) -> bool:
    last_in = _parse(user.get("last_inbound_at") or "")
    if not last_in:
        return False
    return _now() - last_in < timedelta(hours=WINDOW_HOURS)


def cooldown_clear(user: dict[str, Any], key: str = "", direct: bool = False) -> bool:
    if key in SELF_COOLDOWN or direct:
        last_dm = _parse((user.get("last_sent_at") or {}).get(key) or "")
    else:
        last_dm = _parse(user.get("last_dm_at") or "")
    if not last_dm:
        return True
    return _now() - last_dm >= timedelta(minutes=settings.dm_cooldown_minutes)


def library_link(user: dict[str, Any]) -> str:
    token = (user.get("library_token") or "").strip()
    if not token:
        from app.services.auth import get_or_create_library_token

        token = get_or_create_library_token(user["id"])
    base = (settings.public_base_url or "").rstrip("/")
    if not token or not base.startswith("http"):
        return ""
    return f"{base}/g/{token}"


def decide(user: dict[str, Any], trigger: str) -> str | None:
    """Which message, if any. Pure: no sends, no writes, no model.

    `trigger` is what woke us: reel_saved, reel_ready, reel_failed, reel_held,
    already_saved, photo_post, unreadable_share, plain_message, ask_how,
    ask_what, ask_free (and their typed_ variants), delete_request, month_cap,
    timer.
    """
    if trigger == "month_cap":
        # Said once a month, to signed-in accounts too: without it their
        # reels would simply stop saving with no word why.
        last = _parse((user.get("last_sent_at") or {}).get("m10_month_cap") or "")
        return None if last and last >= _month_start() else "m10_month_cap"

    if trigger == "delete_request":
        # Signed in or not: the data deletion page promises this message is
        # enough, to everyone.
        return "m21_delete_ack"

    if user["signed_in"]:
        # Converted. The bot already got what it was for.
        return None

    n = user["reel_count"]
    sent = user["already_sent"]
    candidates: list[str] = []

    if trigger == "reel_saved":
        if n <= 1 and "m1_first_ack" not in sent:
            candidates.append("m1_first_ack")

    if trigger == "reel_held":
        candidates.append("m7_past_lock")

    if trigger == "reel_ready":
        # Only the first reel is announced. After that they have seen the
        # library and know it works, so a message per reel is noise: it was
        # 21 DMs for 21 reels, aimed at someone who needs no reminding
        # because they are actively saving. The bot speaks when they drift,
        # not when they act.
        if "m2_first_library" not in sent:
            candidates.append("m2_first_library")
        # Milestones still fire on the crossing, but each exists once in a
        # lifetime, so the whole set is three messages, not one per reel.
        if n >= LOCK_AT and "m6_lock" not in sent:
            candidates.append("m6_lock")
        elif HEADS_UP_AT <= n < LOCK_AT and "m5_heads_up" not in sent:
            candidates.append("m5_heads_up")
        elif n >= HOME_SCREEN_AT and "m4_home_screen" not in sent:
            candidates.append("m4_home_screen")

    if trigger == "reel_failed":
        # They were told it is processing. Silence here reads as a working
        # save, and the window shuts on it.
        candidates.append("m9_could_not_read")

    if trigger == "unreadable_share":
        # Not their reel at fault but the way it was shared, so the fix they
        # are told is different: copy the link.
        candidates.append("m16_unreadable_share")

    if trigger == "photo_post":
        candidates.append("m15_photo_post")

    if trigger == "already_saved":
        candidates.append("m17_already_saved")

    if trigger in ANSWER_FOR:
        candidates.append(ANSWER_FOR[trigger])

    if trigger == "plain_message":
        # "Here is your library" to someone who has none yet is a button to
        # an empty page. They get how to start instead.
        candidates.append("m8_recovery" if n > 0 else "m11_how_to_save")

    if trigger == "timer":
        candidates.append("m3_quiet_nudge")

    candidates = [c for c in candidates if not (c in ONCE_EVER and c in sent)]
    for key in PRECEDENCE:
        if key in candidates:
            return key
    return None


# Pictographs, dingbats, flags, and the joiners that glue them together.
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U0001F1E6-\U0001F1FF←-⇿⌀-⏿"
    "☀-➿⬀-⯿〰〽㊗㊙️‍⃣]"
)
_DASH_RE = re.compile("—|–|\\s-+\\s|--")


def copy_problems(text: str) -> list[str]:
    """Why a piece of bot copy breaks the house rules, or [] when it is fine.

    No long dashes, no hyphen standing in for one, no emoji, no exclamation
    marks. scripts/simulate_nudges.py fails on any of these, and fire() checks
    again at send time because a reel title is written by a model, not by us.
    """
    problems = []
    if "—" in text:
        problems.append("em dash")
    if "–" in text:
        problems.append("en dash")
    if re.search("\\s-+\\s|--", text):
        problems.append("hyphen used as a dash")
    if "!" in text:
        problems.append("exclamation mark")
    if _EMOJI_RE.search(text):
        problems.append("emoji")
    return problems


def clean_title(title: str) -> str:
    """A reel title made safe to quote back inside a sentence of ours."""
    cleaned = _EMOJI_RE.sub("", title or "")
    cleaned = _DASH_RE.sub(", ", cleaned).replace("!", "")
    cleaned = " ".join(cleaned.split()).strip(" .,;:")
    if len(cleaned) > 80:
        cleaned = cleaned[:80].rsplit(" ", 1)[0].strip(" .,;:")
    return cleaned


def _legacy_text(key: str, user: dict[str, Any], title: str = "") -> str:
    """The plain text each message was before the redesign, link pasted in.

    This is what goes out when Instagram refuses a button message, and what
    everything falls back to with DM_RICH_MESSAGES=0. It worked for every
    guest before buttons existed, which is the point of keeping it.
    """
    link = library_link(user)
    n = user["reel_count"]

    if key == "m2_first_library":
        head = f"Here is your library: {link}"
        if title:
            head = f"Saved it as {title}. Here is your library: {link}"
        return head + " That is 1 of 5. Send a few more and shelves start appearing on your Home."
    if key == "m3_quiet_nudge":
        return f"Still here whenever you find something worth keeping. Your library: {link}"
    if key == "m4_home_screen":
        return f"{n} reels now. Put ClipNest on your home screen so you are not digging through DMs for this link: {link}"
    if key == "m5_heads_up":
        return f"{n} saved. At {LOCK_AT} you will need a free account to keep going. One tap, and everything you have stays exactly where it is."
    if key == "m6_lock":
        return f"That is {LOCK_AT} reels. Sign in to keep saving and it is all still here: {link}"
    if key == "m7_past_lock":
        return f"Holding that one for you. Sign in and it saves straight away: {link}"
    if key == "m9_could_not_read":
        text = "I could not read that one. If it is private, a photo post, or deleted, try another reel."
        return f"{text} Your library: {link}" if link else text
    if key == "m10_month_cap":
        return f"You have hit this month's limit of {settings.monthly_reel_cap} reels. It resets on the 1st."
    if key == "m8_recovery":
        return f"Here is your library: {link}"
    return ""


def _message(text: str, fallback: str = "", buttons: list | None = None, chips: list | None = None) -> dict[str, Any]:
    buttons = [b for b in (buttons or []) if b.get("url")]
    chips = list(chips or [])
    if buttons:
        # A button with nowhere to paste its link as text has no fallback
        # worth sending, so the link rides on the end of the sentence.
        fallback = fallback or f"{text} Your library: {buttons[0]['url']}"
        return {"text": text, "format": "button", "buttons": buttons, "quick_replies": [], "fallback_text": fallback}
    if chips:
        return {"text": text, "format": "quick_replies", "buttons": [], "quick_replies": chips, "fallback_text": fallback or text}
    return {"text": text, "format": "text", "buttons": [], "quick_replies": [], "fallback_text": text}


def render(key: str, user: dict[str, Any], title: str = "", trigger: str = "") -> dict[str, Any]:
    """What to send for a message key: the words, the format, and the plain
    text to fall back to.

    Returns {"text", "format": "text" | "button" | "quick_replies", "buttons",
    "quick_replies", "fallback_text"}. Copy is launch_kit/DM_REDESIGN_SPEC.md
    section 5, verbatim. Static, so it is also what a validator falls back to
    if a model ever writes these.
    """
    link = library_link(user)
    n = user["reel_count"]
    title = clean_title(title)
    legacy = _legacy_text(key, user, title=title)

    def open_library(url: str = link) -> list[dict]:
        return [{"type": "web_url", "title": "Open my library", "url": url}] if link else []

    def sign_in(label: str) -> list[dict]:
        return [{"type": "web_url", "title": label, "url": f"{link}?signin=1"}] if link else []

    if key == "m1_first_ack":
        # Honest about the line. One worker reads one reel at a time, so on a
        # busy night "a few minutes" would be a promise broken for most people
        # who hear it. With nothing much ahead, the short line is true.
        from app.services.jobs import estimated_wait

        wait = estimated_wait(user["id"])
        if wait["ahead"] > 1:
            minutes = max(5, -(-wait["minutes"] // 5) * 5)
            return _message(
                f"Got it. A few reels are ahead of yours, so this one takes about {minutes} minutes. "
                "I will message you here the moment it is ready."
            )
        # No button: there is nothing to open yet, and a button to an empty
        # page is worse than none.
        return _message("Got it. I am watching that reel now. Your library link comes back here in a few minutes.")
    if key == "m2_first_library":
        # No promise tied to a number: shelves appear when a few reels share
        # a subject, which five mixed reels may not.
        head = f"Saved it as {title}." if title else "Saved your first reel."
        return _message(
            f"{head} That is 1 of 5. Send a few more and shelves start appearing on your Home.",
            legacy, buttons=open_library(),
        )
    if key == "m3_quiet_nudge":
        # The only message aimed at someone who is drifting, so it asks for
        # one specific small thing rather than describing the product. No
        # button until there is a library worth opening: the ask is to send.
        if n <= 1:
            if title:
                return _message(f"You saved {title} yesterday. Send me one more and I can start grouping them.")
            return _message("Send me one more reel and I can start grouping them.")
        if n < HOME_SCREEN_AT:
            return _message(f"{n} saved so far. A few more and they sort themselves onto shelves.")
        return _message("Still here whenever you find something worth keeping.", legacy, buttons=open_library())
    if key == "m4_home_screen":
        return _message(
            f"{n} reels in. Put ClipNest on your home screen so this link is never buried in DMs again.",
            legacy, buttons=open_library(f"{link}?hs=prompt"),
        )
    if key == "m5_heads_up":
        return _message(
            f"{n} saved. At {LOCK_AT} I will ask you to sign in with Google, so your library is safe "
            "if this chat ever disappears. One tap, nothing moves.",
            legacy, buttons=sign_in("Sign in now"),
        )
    if key == "m6_lock":
        return _message(
            f"That is {LOCK_AT} reels. Sign in to keep saving. Everything you have stays exactly where it is.",
            legacy, buttons=sign_in("Sign in to keep them"),
        )
    if key == "m7_past_lock":
        held = int(user.get("held_count") or 0)
        if held >= 2:
            return _message(
                f"Holding {held} reels for you. Sign in and they all save at once.",
                f"Holding {held} reels for you. Sign in and they all save at once: {link}",
                buttons=sign_in("Sign in to keep them"),
            )
        return _message(
            "Holding that one for you. Sign in and it saves straight away.",
            legacy, buttons=sign_in("Sign in to keep them"),
        )
    if key == "m8_recovery":
        return _message(
            "Here is your library. Share any reel to this chat and I will add it.",
            legacy, buttons=open_library(),
        )
    if key == "m9_could_not_read":
        text = "I could not read that one. Private, deleted, or a photo post are the usual reasons. Try another reel."
        # On a first reel that fails there is nothing to open, so no button.
        if int(user.get("completed_count") or 0) >= 1:
            return _message(text, legacy, buttons=open_library())
        return _message(text)
    if key == "m10_month_cap":
        return _message(
            f"That is this month's {settings.monthly_reel_cap} reels. New reels save again from the 1st. "
            "Everything already saved is still there.",
            legacy, buttons=open_library(),
        )
    if key == "m11_how_to_save":
        text = (
            "Share any reel to this chat. Tap the paper plane under the reel, search clipnest, send. "
            "I will read it and send your library back in a few minutes."
        )
        return _message(text, chips=QUESTION_CHIPS if trigger.startswith("typed_") else None)
    if key == "m12_what_it_does":
        text = (
            "You send me reels, I watch them and file them by what they are actually about. Then you can "
            'search your own saved reels in plain words, like "cafe in goa" or "that press down exercise".'
        )
        if trigger.startswith("typed_"):
            return _message(text, chips=QUESTION_CHIPS)
        return _message(text, buttons=open_library() if n > 0 else None)
    if key == "m13_is_it_free":
        cap = settings.monthly_reel_cap
        head = f"Yes. Up to {cap} reels a month, free." if cap > 0 else "Yes, it is free."
        text = (
            f"{head} After {LOCK_AT} reels I will ask you to sign in with Google so your library "
            "is safe even if this chat is lost."
        )
        return _message(text, chips=QUESTION_CHIPS if trigger.startswith("typed_") else None)
    if key == "m15_photo_post":
        return _message("That is a photo post, not a reel. I only read reels for now.")
    if key == "m16_unreadable_share":
        return _message(
            "I could not find the reel in that message. Open the reel, tap the three dots, Copy link, and paste it here.",
            chips=HOW_TO_SHARE_CHIP,
        )
    if key == "m17_already_saved":
        text = "You already have that one. It is in your library"
        text = f"{text} as {title}." if title else f"{text}."
        return _message(text, buttons=open_library())
    if key == "m21_delete_ack":
        return _message("Got it. Your data will be deleted within 7 days. You will get a message here when it is done.")
    return _message("")


def _pause(seconds: float) -> None:
    time.sleep(seconds)


def _show_typing(igsid: str, key: str) -> None:
    """ "Seen", then the dots for a second or two, like a person replying.
    Decoration: if either call fails the message simply goes straight out."""
    try:
        if not send_sender_action(igsid, "mark_seen", timeout=SENDER_ACTION_TIMEOUT_SECONDS)["ok"]:
            return
        if not send_sender_action(igsid, "typing_on", timeout=SENDER_ACTION_TIMEOUT_SECONDS)["ok"]:
            return
        _pause(TYPING_SECONDS.get(key, TYPING_SECONDS_DEFAULT))
    except Exception:
        pass


def _deliver(igsid: str, key: str, message: dict[str, Any]) -> tuple[dict, bool]:
    """Send one rendered message. Returns (result, fell_back_to_text).

    A person must never hear nothing because a template was rejected: any
    failure of the rich form is followed by the plain text one.
    """
    if not settings.dm_rich_messages:
        return send_text(igsid, message["fallback_text"]), False
    _show_typing(igsid, key)
    if message["format"] == "button":
        rich = send_button_template(igsid, message["text"], message["buttons"])
    elif message["format"] == "quick_replies":
        rich = send_quick_replies(igsid, message["text"], message["quick_replies"])
    else:
        return send_text(igsid, message["text"]), False
    if rich["ok"]:
        return rich, False
    result = send_text(igsid, message["fallback_text"])
    result = {"ok": result["ok"], "detail": f"{message['format']} refused ({rich['detail']}) :: text {result['detail']}"}
    return result, True


def fire(user_id: str, trigger: str, title: str = "", direct: bool = False) -> str | None:
    """Decide, send, record. Returns the message key actually sent, or None.

    The only entry point. Callers say what happened, never what to send.
    `direct` marks an answer to a tap: it is judged against the last time the
    same answer went out, so tapping two questions in a row gets two answers.
    """
    try:
        user = load_state(user_id)
        if not user:
            return None
        igsid = (user.get("instagram_user_id") or "").strip()
        if not igsid:
            return None
        if not replies_allowed(user):
            log_event("nudge", igsid, "skipped_gate", f"{user_id} not on an allowlist")
            return None
        if not window_open(user):
            log_event("nudge", igsid, "skipped_window", f"{user_id} last inbound {user.get('last_inbound_at')!r}")
            return None

        key = decide(user, trigger)
        if not key:
            return None
        # Cooldown exists to stop a repeatable message firing in a burst. A
        # once-ever message can, by construction, never repeat - so applying
        # it there only breaks the opening pair on purpose: M1 fires
        # instantly, M2 fires a few minutes later once processing finishes,
        # and 10 minutes is comfortably inside that gap. This was silently
        # eating M2 for every single guest.
        if key not in ONCE_EVER and not cooldown_clear(user, key, direct=direct):
            log_event("nudge", igsid, "skipped_cooldown", f"{user_id} last dm {user.get('last_dm_at')!r}")
            return None
        message = render(key, user, title=title, trigger=trigger)
        if title and _message_problems(message):
            # The title is the only part of a message we did not write.
            message = render(key, user, trigger=trigger)
        if not message["text"] or (key in NEEDS_LINK and not library_link(user)):
            log_event("nudge", igsid, "skipped", f"{key} produced no usable text")
            return None

        result, fell_back = _deliver(igsid, key, message)
        if result["ok"]:
            now = _iso(_now())
            with get_connection() as connection:
                connection.execute(
                    "UPDATE users SET last_dm_at = ? WHERE id = ?", (now, user_id)
                )
                connection.execute(
                    "INSERT INTO nudge_log (user_id, message_key, sent_at, detail) VALUES (?, ?, ?, ?)",
                    (user_id, key, now, (title or "")[:120]),
                )
        outcome = "send_failed"
        if result["ok"]:
            outcome = "fallback_text" if fell_back else "sent"
        log_event("nudge", igsid, outcome, f"{key} trigger={trigger} :: {result['detail']}")
        return key if result["ok"] else None
    except Exception as exc:
        log_event("nudge", "", "nudge_crashed", f"{user_id} {trigger} :: {exc}")
        return None


def _message_problems(message: dict[str, Any]) -> list[str]:
    """Every rule a rendered message breaks, labels included."""
    problems = copy_problems(message.get("text") or "")
    for item in (message.get("buttons") or []) + (message.get("quick_replies") or []):
        label = item.get("title") or ""
        problems += copy_problems(label)
        if len(label) > MAX_BUTTON_TITLE_CHARS:
            problems.append(f"label over {MAX_BUTTON_TITLE_CHARS} characters: {label!r}")
    return problems


def due_for_last_call(limit: int = 20) -> list[str]:
    """Users sitting at 23 hours since their last message, not yet nudged.

    Anchored to the most recent inbound, never to their first reel: the window
    resets on every message they send, so anchoring to the first reel would
    fire hours early and waste the only shot left.
    """
    now = _now()
    lower = _iso(now - timedelta(hours=WINDOW_HOURS))
    upper = _iso(now - timedelta(hours=LAST_CALL_AFTER_HOURS))
    try:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT u.id FROM users u
                WHERE u.last_inbound_at != ''
                  AND u.last_inbound_at <= ?
                  AND u.last_inbound_at > ?
                  AND COALESCE(u.google_sub, '') = ''
                  AND u.instagram_user_id != ''
                  AND NOT EXISTS (
                    SELECT 1 FROM nudge_log n
                    WHERE n.user_id = u.id AND n.message_key = 'm3_quiet_nudge'
                      AND n.sent_at > u.last_inbound_at
                  )
                LIMIT ?
                """,
                (upper, lower, limit),
            ).fetchall()
        return [r["id"] for r in rows]
    except Exception:
        return []


def run_last_call_sweep() -> int:
    """Called from the janitor loop. Almost always does nothing, cheaply."""
    sent = 0
    for user_id in due_for_last_call():
        title = ""
        try:
            with get_connection() as connection:
                row = connection.execute(
                    "SELECT ri.item_name FROM reel_items ri JOIN reels r ON r.id = ri.reel_id "
                    "WHERE r.user_id = ? AND ri.item_name != '' ORDER BY r.received_at DESC LIMIT 1",
                    (user_id,),
                ).fetchone()
            title = row["item_name"] if row else ""
        except Exception:
            pass
        if fire(user_id, "timer", title=title):
            sent += 1
    return sent
