"""Run every situation in NUDGE_RULEBOOK.md against the real nudge code and
print what actually gets sent.

This exists so a change can be verified in seconds against a throwaway
database instead of by waiting real hours or burning a real Instagram
account. It calls app.services.nudge.fire() - the exact function production
calls - with the Instagram send calls replaced by recorders, so what you see
here is provably what the live code would do, not a description of intent.

It is also the copy check. The run fails (exit code 1) if any message breaks
the house rules (a long dash, a hyphen used as one, an emoji, an exclamation
mark), if any button or chip label is over 20 characters, or if any message
the code can send never appeared in a scenario.

Usage:
    QUEUE_JANITOR=off python3 scripts/simulate_nudges.py
    QUEUE_JANITOR=off python3 scripts/simulate_nudges.py --markdown report.md
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

os.environ.setdefault("SESSION_SECRET", "simulate")
os.environ.setdefault("PUBLIC_BASE_URL", "https://clipnest.in")
os.environ.setdefault("GUEST_TEST_SENDERS", "sim_user")
os.environ.setdefault("DM_COOLDOWN_MINUTES", "10")
os.environ.setdefault("GUEST_LOCK_ENABLED", "1")

_tmp = tempfile.mkdtemp(prefix="clipnest_nudge_sim_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/sim.db"
os.environ["STORAGE_DIR"] = f"{_tmp}/storage"
os.environ["MEDIA_DIR"] = f"{_tmp}/media"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.init_db import initialize_database  # noqa: E402
from app.db.database import get_connection  # noqa: E402
from app.services import nudge  # noqa: E402
from app.services.auth import create_guest_user, iso_now  # noqa: E402

initialize_database()

SENT: list[dict] = []
ACTIONS: list[str] = []  # "seen", typing dots and pauses, in the order they happened
REFUSE_TEMPLATES = False  # flipped on to act out Instagram rejecting a button message


def _record_text(igsid: str, text: str) -> dict:
    SENT.append({"format": "text", "text": text, "labels": [], "before": list(ACTIONS)})
    ACTIONS.clear()
    return {"ok": True, "detail": "simulated"}


def _record_buttons(igsid: str, text: str, buttons: list) -> dict:
    if REFUSE_TEMPLATES:
        return {"ok": False, "detail": "http_400: simulated refusal"}
    SENT.append({"format": "button", "text": text, "labels": [b["title"] for b in buttons],
                 "urls": [b.get("url", "") for b in buttons], "before": list(ACTIONS)})
    ACTIONS.clear()
    return {"ok": True, "detail": "simulated"}


def _record_chips(igsid: str, text: str, replies: list) -> dict:
    if REFUSE_TEMPLATES:
        return {"ok": False, "detail": "http_400: simulated refusal"}
    SENT.append({"format": "quick_replies", "text": text, "labels": [r["title"] for r in replies], "before": list(ACTIONS)})
    ACTIONS.clear()
    return {"ok": True, "detail": "simulated"}


def _record_action(igsid: str, action: str, timeout: float = 0) -> dict:
    ACTIONS.append(action)
    return {"ok": True, "detail": "simulated"}


# The only things faked: the actual Graph calls, and the wait for the dots.
nudge.send_text = _record_text
nudge.send_button_template = _record_buttons
nudge.send_quick_replies = _record_chips
nudge.send_sender_action = _record_action
nudge._pause = lambda seconds: ACTIONS.append(f"pause {seconds}s")

TITLES = [
    "Triceps Press Down", "Banaras Cafe", "Goa Hostel", "AI Video Editing",
    "Paneer Tikka Recipe", "Boxing Drill", "Hampi Trek Guide",
]


def _ago(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")


def _stamp(user_id: str, **cols) -> None:
    with get_connection() as c:
        sets = ", ".join(f"{k} = ?" for k in cols)
        c.execute(f"UPDATE users SET {sets} WHERE id = ?", (*cols.values(), user_id))


def _clear_cooldown(user_id: str) -> None:
    """Backdate last_dm_at so the next fire() is judged on its own, not on
    whatever message a previous scenario happened to send a moment ago.
    Real users have hours between most messages; a test script run in one
    process does not, unless told to."""
    _stamp(user_id, last_dm_at=_ago(1))


def _add_reel(user_id: str, n: int, title: str) -> None:
    now = iso_now()
    with get_connection() as c:
        c.execute(
            "INSERT INTO reels (id,user_id,url,received_at,status,created_at,updated_at) "
            "VALUES (?,?,?,?, 'completed',?,?)",
            (f"{user_id}_r{n}", user_id, f"u{n}", now, now, now),
        )
        c.execute(
            "INSERT INTO reel_items (reel_id,item_name,created_at) VALUES (?,?,?)",
            (f"{user_id}_r{n}", title, now),
        )


def _fresh_guest(tag: str) -> str:
    igsid = f"sim_{tag}"
    u = create_guest_user(igsid, "sim_user")
    nudge.record_inbound(igsid)
    return u["id"]


def _fresh_guest_with_reel(tag: str) -> str:
    user_id = _fresh_guest(tag)
    _add_reel(user_id, 1, TITLES[0])
    return user_id


ROWS: list[tuple[str, str, str]] = []  # (situation, condition, reply)


def _show(message: dict) -> str:
    """One sent message as a person would see it: [a button], (a chip)."""
    shown = message["text"]
    for label in message["labels"]:
        shown += f" [{label}]" if message["format"] == "button" else f" ({label})"
    return shown


def run(situation: str, condition: str, fn) -> None:
    before = len(SENT)
    fn()
    reply = _show(SENT[-1]) if len(SENT) > before else "(nothing sent)"
    ROWS.append((situation, condition, reply))


# --- 1. The opening, reel by reel -----------------------------------------
uid = _fresh_guest("walkthrough")

run("Reel 1 saved (before processing)", "instant, on save",
    lambda: nudge.fire(uid, "reel_saved"))

_add_reel(uid, 1, TITLES[0])
run("Reel 1 finishes processing", "once ever, carries 1-of-5",
    lambda: nudge.fire(uid, "reel_ready", title=TITLES[0]))

for n in (2, 3, 4):
    _add_reel(uid, n, TITLES[n % len(TITLES)])
    nudge.record_inbound(f"sim_walkthrough")
    run(f"Reel {n} finishes processing", "active, not a milestone",
        lambda n=n: nudge.fire(uid, "reel_ready", title=TITLES[n % len(TITLES)]))

_add_reel(uid, 5, TITLES[5 % len(TITLES)])
run("Reel 5 finishes processing", "crosses the home-screen line",
    lambda: nudge.fire(uid, "reel_ready", title=TITLES[0]))

for n in range(6, 17):
    _add_reel(uid, n, TITLES[n % len(TITLES)])
run("Reels 6 through 16 finish", "11 reels, all silent (shown once)",
    lambda: nudge.fire(uid, "reel_ready", title="irrelevant"))

_add_reel(uid, 17, TITLES[0])
run("Reel 17 finishes processing", "crosses the heads-up line",
    lambda: nudge.fire(uid, "reel_ready", title=TITLES[0]))

for n in (18, 19):
    _add_reel(uid, n, TITLES[n % len(TITLES)])
run("Reels 18 and 19 finish", "silent", lambda: nudge.fire(uid, "reel_ready", title="x"))

_add_reel(uid, 20, TITLES[0])
run("Reel 20 finishes processing", "hits the lock",
    lambda: nudge.fire(uid, "reel_ready", title=TITLES[0]))

_clear_cooldown(uid)  # otherwise this is testing cooldown-after-m6, not the lock
run("Reel 21 arrives", "GUEST_LOCK_ENABLED=1: held, not processed",
    lambda: (nudge.fire(uid, "reel_held") if nudge.is_locked(uid) else None))

with get_connection() as c:
    processed = c.execute("SELECT COUNT(*) FROM reels WHERE user_id=?", (uid,)).fetchone()[0]
ROWS.append(("Reels actually processed after 21 sends", f"{processed} (the 21st was held, costs nothing)", "-"))

# --- 2. Going quiet, and coming back ----------------------------------------
uid2 = _fresh_guest("quiet")
_add_reel(uid2, 1, TITLES[0])
_stamp(uid2, last_inbound_at=_ago(23.5), last_dm_at="")
run("23 hours since their last message, 1 reel saved", "the quiet nudge, early-journey wording",
    lambda: nudge.run_last_call_sweep())

run("The 150s sweep runs again immediately after", "same dormancy: must stay silent",
    lambda: nudge.run_last_call_sweep())

nudge.record_inbound(f"sim_quiet")
_stamp(uid2, last_inbound_at=_ago(23.5), last_dm_at="")
run("They replied, then went quiet again", "fresh dormancy: nudges again",
    lambda: nudge.run_last_call_sweep())

uid3 = _fresh_guest("quiet_mid")
for n in range(1, 4):
    _add_reel(uid3, n, TITLES[n])
_stamp(uid3, last_inbound_at=_ago(23.5), last_dm_at="")
run("23 hours quiet, 3 reels saved (short of 5)", "quiet nudge, mid-journey wording",
    lambda: nudge.run_last_call_sweep())

uid4 = _fresh_guest("quiet_active")
for n in range(1, 9):
    _add_reel(uid4, n, TITLES[n % len(TITLES)])
_stamp(uid4, last_inbound_at=_ago(23.5), last_dm_at="")
run("23 hours quiet, 8 reels saved (past 5)", "quiet nudge, established-library wording",
    lambda: nudge.run_last_call_sweep())

uid5 = _fresh_guest("unreachable")
_add_reel(uid5, 1, TITLES[0])
_stamp(uid5, last_inbound_at=_ago(25), last_dm_at="")
run("25 hours since their last message", "window is shut: permanently silent",
    lambda: nudge.run_last_call_sweep())

# --- 3b. A reel that could not be read ---------------------------------------
uid10 = _fresh_guest("first_fails")
nudge.fire(uid10, "reel_saved")
run("Their first reel fails two minutes after the ack", "must not be eaten by the cooldown the ack just started",
    lambda: nudge.fire(uid10, "reel_failed"))
run("A second reel fails right after", "one failure reply per cooldown, not one per reel",
    lambda: nudge.fire(uid10, "reel_failed"))

uid11 = _fresh_guest("unreadable")
_add_reel(uid11, 1, TITLES[0])
nudge.fire(uid11, "reel_ready", title=TITLES[0])
run("They share a reel the bot cannot find a link in", "says it did not save, and how to send it instead",
    lambda: nudge.fire(uid11, "unreadable_share"))

# --- 3c. A busy night: the first reply states the real wait ------------------
def _queue_job(user_id: str, reel_id: str) -> None:
    now = iso_now()
    with get_connection() as c:
        c.execute(
            "INSERT INTO reels (id,user_id,url,received_at,status,created_at,updated_at) "
            "VALUES (?,?,?,?, 'pending',?,?)", (reel_id, user_id, reel_id, now, now, now),
        )
        c.execute(
            "INSERT INTO processing_jobs (reel_id,user_id,job_type,status,attempts,error_message,"
            "created_at,started_at,finished_at) VALUES (?,?, 'process_reel','pending',0,'',?,'','')",
            (reel_id, user_id, now),
        )


for i in range(12):
    _queue_job(_fresh_guest(f"busy{i}"), f"busy_reel_{i}")
uid12 = _fresh_guest("busy_last")
_queue_job(uid12, "busy_reel_last")
run("First reel, with 12 other new people's reels ahead of it", "says the real wait (2 minutes a reel, rounded up to 5)",
    lambda: nudge.fire(uid12, "reel_saved"))
with get_connection() as c:
    c.execute("DELETE FROM processing_jobs")

# --- 4. The gates ------------------------------------------------------------
with get_connection() as c:
    now = iso_now()
    c.execute(
        "INSERT INTO users (id,telegram_user_id,display_name,created_at,email,"
        "instagram_user_id,instagram_username,last_login_at,updated_at) "
        "VALUES ('sim_not_allowed',NULL,'N',?, '','not_allowed_handle','not_allowed_handle',?,?)",
        (now, now, now),
    )
    c.execute(
        "INSERT INTO reels (id,user_id,url,received_at,status,created_at,updated_at) "
        "VALUES ('nar1','sim_not_allowed','u',?, 'completed',?,?)", (now, now, now),
    )
    c.execute("INSERT INTO reel_items (reel_id,item_name,created_at) VALUES ('nar1','X',?)", (now,))
nudge.record_inbound("sim_not_allowed")
run("A real user, not in GUEST_TEST_SENDERS, saves a reel", "the gate that protects everyone else",
    lambda: nudge.fire("sim_not_allowed", "reel_ready", title="X"))

uid7 = _fresh_guest("converted")
_add_reel(uid7, 1, TITLES[0])
_stamp(uid7, google_sub="g_signed_in_123")
run("A converted user (signed in with Google) saves another reel", "the bot already got what it wanted",
    lambda: nudge.fire(uid7, "reel_ready", title=TITLES[1]))

uid8 = _fresh_guest("second_reel")
_add_reel(uid8, 1, TITLES[0])
nudge.fire(uid8, "reel_ready", title=TITLES[0])
_add_reel(uid8, 2, TITLES[1])
run("Reel 2 finishes a moment after reel 1", "not a milestone: silent regardless of cooldown",
    lambda: nudge.fire(uid8, "reel_ready", title=TITLES[1]))

uid9 = _fresh_guest("lock_burst")
with get_connection() as c:
    now = iso_now()
    for n in range(1, 21):
        c.execute("INSERT INTO reels (id,user_id,url,received_at,status,created_at,updated_at) "
                   "VALUES (?,?,?,?, 'completed',?,?)", (f"{uid9}_r{n}", uid9, f"u{n}", now, now, now))
nudge.fire(uid9, "reel_ready", title=TITLES[0])  # m6_lock, sets last_dm_at
run("A second reel is held seconds after the lock fires", "repeatable M7 respects cooldown: correctly silent",
    lambda: nudge.fire(uid9, "reel_held"))


# --- 5. Replies to things they sent ----------------------------------------
uid15 = _fresh_guest("dupe")
_add_reel(uid15, 1, TITLES[0])
run("Sends a reel they already saved", "nothing queued or paid for; the title is not quoted",
    lambda: nudge.fire(uid15, "already_saved", title=TITLES[0]))
uid15b = _fresh_guest("dupe_untitled")
_add_reel(uid15b, 1, "")
run("Sends a reel they already saved, which has no title", "same reply: titles are never quoted",
    lambda: nudge.fire(uid15b, "already_saved"))

uid16 = _fresh_guest("photo")
run("They share a post or a photo instead of a reel", "told reels only; a pasted /p/ link still saves, most were videos",
    lambda: nudge.fire(uid16, "photo_post"))

uid17 = _fresh_guest("fail_with_library")
_add_reel(uid17, 1, TITLES[0])
nudge.fire(uid17, "reel_ready", title=TITLES[0])
run("A later reel fails, and they already have a library", "the failure reply carries the library button",
    lambda: nudge.fire(uid17, "reel_failed"))

uid18 = _fresh_guest("delete_guest")
_add_reel(uid18, 1, TITLES[0])
run("Types 'delete my data'", "acknowledged only; the deleting is done by hand from the health page",
    lambda: nudge.fire(uid18, "delete_request"))
uid19 = _fresh_guest("delete_signed_in")
_stamp(uid19, google_sub="g_signed_in_456")
run("A signed in user types 'delete my data'", "the one question a signed in user is always answered on",
    lambda: nudge.fire(uid19, "delete_request"))

uid20 = _fresh_guest("cap")
_add_reel(uid20, 1, TITLES[0])
run("Their 51st reel of the month arrives", "said once a month; the reel is not read or paid for",
    lambda: nudge.fire(uid20, "month_cap"))
run("A 52nd arrives", "already told this month: silent",
    lambda: nudge.fire(uid20, "month_cap"))

uid21 = _fresh_guest("held_many")
with get_connection() as c:
    now = iso_now()
    for n in range(1, 21):
        c.execute("INSERT INTO reels (id,user_id,url,received_at,status,created_at,updated_at) "
                   "VALUES (?,?,?,?, 'completed',?,?)", (f"{uid21}_r{n}", uid21, f"u{n}", now, now, now))
    for n in range(3):
        c.execute("INSERT INTO instagram_webhook_events (received_at,kind,sender_id,outcome,detail) "
                   "VALUES (?, 'reel', 'sim_held_many', 'buffered', ?)", (now, f"https://www.instagram.com/reel/held{n}/"))
run("Three reels arrive at once past the lock", "one message, carrying the count",
    lambda: nudge.fire(uid21, "reel_held"))

uid25 = _fresh_guest("returner")
for n in range(1, 4):
    _add_reel(uid25, n, TITLES[n])
run("A guest sends a reel after 10 days without one", "welcome back, since later reels are otherwise silent",
    lambda: nudge.fire(uid25, "reel_returned"))
uid26 = _fresh_guest("returner_new")
run("A brand new person's first reel counts as returning", "the first reel acknowledgement wins",
    lambda: nudge.fire(uid26, "reel_returned"))
uid27 = _fresh_guest("member_fail")
_add_reel(uid27, 1, TITLES[0])
_stamp(uid27, google_sub="g_member_fail")
run("A signed in user's reel cannot be read", "told, with their library button",
    lambda: nudge.fire(uid27, "reel_failed"))


# --- 6. Instagram refuses a button message -----------------------------------
uid22 = _fresh_guest("refused")
_add_reel(uid22, 1, TITLES[0])
REFUSE_TEMPLATES = True
run("First library message, but Instagram rejects the button", "falls back to the plain text with the link, never silence",
    lambda: nudge.fire(uid22, "reel_ready", title=TITLES[0]))
uid23 = _fresh_guest("refused_chips")
run("Unreadable share, but Instagram rejects the chips", "same words go out as plain text",
    lambda: nudge.fire(uid23, "unreadable_share"))
REFUSE_TEMPLATES = False

# --- checks ------------------------------------------------------------------
def problems() -> list[str]:
    found: list[str] = []
    for message in SENT:
        for issue in nudge.copy_problems(message["text"]):
            found.append(f"{issue} in: {message['text']}")
        for label in message["labels"]:
            for issue in nudge.copy_problems(label):
                found.append(f"{issue} in label: {label}")
            if len(label) > 20:
                found.append(f"label over 20 characters ({len(label)}): {label}")
        if len(message["text"].encode("utf-8")) > (640 if message["format"] == "button" else 1000):
            found.append(f"too long for a {message['format']} message: {message['text'][:60]}")
        if "telegram" in message["text"].lower():
            found.append(f"mentions Telegram: {message['text']}")
        if message["format"] != "text" and "://" in message["text"]:
            found.append(f"a raw link inside a {message['format']} message: {message['text']}")
        if message["before"][:2] != ["mark_seen", "typing_on"] or not message["before"][-1].startswith("pause"):
            found.append(f"sent without seen, typing dots and a pause first: {message['text'][:60]}")
    with get_connection() as c:
        logged = {row[0] for row in c.execute("SELECT DISTINCT message_key FROM nudge_log")}
    never = [key for key in nudge.PRECEDENCE if key not in logged]
    if never:
        found.append(f"no scenario ever sent: {', '.join(never)}")
    return found


# --- report ------------------------------------------------------------------
def to_markdown() -> str:
    lines = [
        "# Nudge scenarios, run against the live code",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by "
        "`scripts/simulate_nudges.py` against a throwaway database. Every reply below came "
        "from `app.services.nudge.fire()`, the exact function production calls; only the "
        "Instagram Graph calls themselves were replaced with recorders. Re-run this after any "
        "change to `app/services/nudge.py` to see every situation at once.",
        "",
        "`[Open my library]` is a button under the message. `(Is it free)` is a chip above the "
        "keyboard. Before every message the person sees \"seen\" and then the typing dots.",
        "",
        "| Situation | Condition | What gets sent |",
        "|---|---|---|",
    ]
    for situation, condition, reply in ROWS:
        reply_cell = reply.replace("|", "\\|")
        lines.append(f"| {situation} | {condition} | {reply_cell} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown", help="write the report to this file instead of stdout")
    args = parser.parse_args()

    report = to_markdown()
    if args.markdown:
        with open(args.markdown, "w") as f:
            f.write(report)
        print(f"wrote {len(ROWS)} scenarios to {args.markdown}")
    else:
        print(report)

    found = problems()
    for issue in found:
        print(f"FAIL: {issue}", file=sys.stderr)
    if found:
        sys.exit(1)
    print(f"copy check passed: {len(SENT)} messages covering all {len(nudge.PRECEDENCE)} message kinds", file=sys.stderr)


if __name__ == "__main__":
    main()
