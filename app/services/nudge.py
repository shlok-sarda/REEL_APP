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

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.db.database import get_connection
from app.services.instagram_send import send_text

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
    "m6_lock",
    "m5_heads_up",
    "m4_home_screen",
    "m7_past_lock",
    "m2_first_library",
    "m1_first_ack",
    "m9_could_not_read",
    "m8_recovery",
    "m3_quiet_nudge",
]

ONCE_EVER = {"m1_first_ack", "m2_first_library", "m4_home_screen", "m5_heads_up", "m6_lock"}

# Judged against the last time the SAME message went out, not against the
# last DM of any kind. The failure reply usually follows the first-reel ack by
# a minute or two, so the shared cooldown would swallow exactly the case it
# exists for: "give me a few minutes", then silence. Measuring it against
# itself still stops ten bad links producing ten replies.
SELF_COOLDOWN = {"m9_could_not_read"}

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
    user = dict(row)
    user["reel_count"] = int(reel_count or 0)
    user["already_sent"] = sent
    user["last_sent_at"] = last_sent
    user["signed_in"] = bool((row["google_sub"] or "").strip())
    return user


def window_open(user: dict[str, Any]) -> bool:
    last_in = _parse(user.get("last_inbound_at") or "")
    if not last_in:
        return False
    return _now() - last_in < timedelta(hours=WINDOW_HOURS)


def cooldown_clear(user: dict[str, Any], key: str = "") -> bool:
    if key in SELF_COOLDOWN:
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

    `trigger` is what woke us: reel_saved, reel_ready, reel_failed,
    unreadable_share, plain_message, timer.
    """
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

    if trigger in {"reel_failed", "unreadable_share"}:
        # They were told it is processing (or think they saved something).
        # Silence here reads as a working save, and the window shuts on it.
        candidates.append("m9_could_not_read")

    if trigger == "plain_message":
        candidates.append("m8_recovery")

    if trigger == "timer":
        candidates.append("m3_quiet_nudge")

    candidates = [c for c in candidates if not (c in ONCE_EVER and c in sent)]
    for key in PRECEDENCE:
        if key in candidates:
            return key
    return None


def render(key: str, user: dict[str, Any], title: str = "") -> str:
    """Static copy, exactly as approved in the rulebook. Also the fallback the
    validator falls back to once a model is writing these."""
    link = library_link(user)
    n = user["reel_count"]

    if key == "m1_first_ack":
        # Honest about the line. One worker reads one reel at a time, so on a
        # busy night "a few minutes" would be a promise broken for most people
        # who hear it. With nothing much ahead, the short line is true.
        from app.services.jobs import estimated_wait

        wait = estimated_wait(user["id"])
        if wait["ahead"] > 1:
            minutes = max(5, -(-wait["minutes"] // 5) * 5)
            return (
                "Thank you for saving a reel with me. A few reels are ahead of yours, "
                f"so it will take about {minutes} minutes. I will message you the moment it is ready."
            )
        return "Thank you for saving a reel with me. It is processing now, give me a few minutes."
    if key == "m2_first_library":
        head = f"Here is your library: {link}"
        if title:
            head = f"Saved it as {title}. Here is your library: {link}"
        # No promise tied to a number: shelves appear when a few reels share
        # a subject, which five mixed reels may not.
        return head + " That is 1 of 5. Send a few more and shelves start appearing on your Home."
    if key == "m3_quiet_nudge":
        # The only message aimed at someone who is drifting, so it asks for
        # one specific small thing rather than describing the product.
        if n <= 1:
            if title:
                return f"You saved {title} yesterday. Send me one more and I can start grouping them for you."
            return "Send me one more reel and I can start grouping them for you."
        if n < HOME_SCREEN_AT:
            return f"{n} saved so far. A few more and it sorts them onto shelves for you."
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
    if key == "m8_recovery":
        return f"Here is your library: {link}"
    return ""


def fire(user_id: str, trigger: str, title: str = "") -> str | None:
    """Decide, send, record. Returns the message key actually sent, or None.

    The only entry point. Callers say what happened, never what to send.
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
        if key not in ONCE_EVER and not cooldown_clear(user, key):
            log_event("nudge", igsid, "skipped_cooldown", f"{user_id} last dm {user.get('last_dm_at')!r}")
            return None
        text = render(key, user, title=title)
        if not text or "://" in text and not library_link(user):
            log_event("nudge", igsid, "skipped", f"{key} produced no usable text")
            return None

        result = send_text(igsid, text)
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
        log_event(
            "nudge", igsid,
            "sent" if result["ok"] else "send_failed",
            f"{key} trigger={trigger} :: {result['detail']}",
        )
        return key if result["ok"] else None
    except Exception as exc:
        log_event("nudge", "", "nudge_crashed", f"{user_id} {trigger} :: {exc}")
        return None


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
