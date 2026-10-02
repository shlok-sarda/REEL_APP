"""Run every situation in NUDGE_RULEBOOK.md against the real nudge code and
print what actually gets sent.

This exists so a change can be verified in seconds against a throwaway
database instead of by waiting real hours or burning a real Instagram
account. It calls app.services.nudge.fire() - the exact function production
calls - with send_text replaced by a recorder, so what you see here is
provably what the live code would do, not a description of intent.

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

SENT: list[str] = []


def _record(igsid: str, text: str) -> dict:
    SENT.append(text)
    return {"ok": True, "detail": "simulated"}


nudge.send_text = _record  # the only thing faked: the actual Graph call

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


ROWS: list[tuple[str, str, str]] = []  # (situation, condition, reply)


def run(situation: str, condition: str, fn) -> None:
    before = len(SENT)
    fn()
    reply = SENT[-1] if len(SENT) > before else "(nothing sent)"
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

# --- 3. Recovery -------------------------------------------------------------
uid6 = _fresh_guest("recovery")
_add_reel(uid6, 1, TITLES[0])
nudge.fire(uid6, "reel_ready", title=TITLES[0])
_clear_cooldown(uid6)
run("They send a message with no reel in it", "the DM thread is the only way back in",
    lambda: nudge.fire(uid6, "plain_message"))

uid6b = _fresh_guest("recovery_burst")
_add_reel(uid6b, 1, TITLES[0])
nudge.fire(uid6b, "reel_ready", title=TITLES[0])
run("They send a no-reel message seconds after the library link", "cooldown correctly suppresses the repeat",
    lambda: nudge.fire(uid6b, "plain_message"))

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


# --- report ------------------------------------------------------------------
def to_markdown() -> str:
    lines = [
        "# Nudge scenarios, run against the live code",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by "
        "`scripts/simulate_nudges.py` against a throwaway database. Every reply below came "
        "from `app.services.nudge.fire()`, the exact function production calls; only the "
        "Instagram Graph call itself was replaced with a recorder. Re-run this after any "
        "change to `app/services/nudge.py` to see every situation at once.",
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


if __name__ == "__main__":
    main()
