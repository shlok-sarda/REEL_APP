"""Post real-shaped Instagram deliveries at the webhook and check what the bot
decides to say back.

scripts/simulate_nudges.py proves the wording. This proves the routing: that a
tapped button, a tapped chip, a typed question, a heart, a duplicate reel and
the words "delete my data" each reach the right reply, through the same
FastAPI route production uses. Nothing leaves the machine: the Instagram send
calls are recorders and the database is a throwaway.

Usage:
    QUEUE_JANITOR=off python3 scripts/test_dm_webhook.py
"""

from __future__ import annotations

import os
import sys
import tempfile

os.environ["QUEUE_JANITOR"] = "off"
os.environ["SESSION_SECRET"] = "webhook-test"
os.environ["PUBLIC_BASE_URL"] = "https://clipnest.in"
os.environ["GUEST_AUTOCREATE_FOR_EVERYONE"] = "1"
os.environ["DM_REPLY_FOR_EVERYONE"] = "1"
os.environ["GUEST_LOCK_ENABLED"] = "1"
os.environ["APP_V2_FOR_EVERYONE"] = "1"
os.environ["DM_RICH_MESSAGES"] = "1"
os.environ["OUTBOUND_DM_TEST"] = "0"
os.environ["APP_ENV"] = "development"
os.environ["INSTAGRAM_APP_SECRET"] = ""
os.environ["INSTAGRAM_ACCESS_TOKEN"] = ""
os.environ["OPENAI_API_KEY"] = "test-key-not-real"

_tmp = tempfile.mkdtemp(prefix="clipnest_dm_webhook_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["STORAGE_DIR"] = f"{_tmp}/storage"
os.environ["MEDIA_DIR"] = f"{_tmp}/media"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.routes import instagram as route  # noqa: E402
from app.db.database import get_connection  # noqa: E402
from app.main import app  # noqa: E402
from app.services import nudge  # noqa: E402

FIRED: list[dict] = []  # every call the route made into the nudge code
SENT: list[dict] = []  # every message that would have gone to Instagram

_real_fire = nudge.fire


def _fire(user_id, trigger, title="", direct=False):
    key = _real_fire(user_id, trigger, title, direct)
    FIRED.append({"trigger": trigger, "title": title, "direct": direct, "sent": key})
    return key


def _sync(func, *args):
    func(*args)


def _text(igsid, text):
    SENT.append({"format": "text", "text": text, "labels": []})
    return {"ok": True, "detail": "test"}


def _buttons(igsid, text, buttons):
    SENT.append({"format": "button", "text": text, "labels": [b["title"] for b in buttons], "urls": [b["url"] for b in buttons]})
    return {"ok": True, "detail": "test"}


def _chips(igsid, text, replies):
    SENT.append({"format": "quick_replies", "text": text, "labels": [r["title"] for r in replies]})
    return {"ok": True, "detail": "test"}


nudge.fire = _fire
nudge.send_text = _text
nudge.send_button_template = _buttons
nudge.send_quick_replies = _chips
nudge.send_sender_action = lambda igsid, action, timeout=0: {"ok": True, "detail": "test"}
nudge._pause = lambda seconds: None
route._reply_later = _sync  # replies run inline so each post can be checked straight after
route.fill_username_for_sender = lambda sender_id: None  # a network lookup
route.ensure_background_progress = lambda: None  # would start the reel worker
route.send_text = _text

CHECKS = 0
FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(f"{name} {detail}".strip())
        print(f"FAIL  {name}  {detail}")
    else:
        print(f"ok    {name}")


def deliver(client: TestClient, event: dict) -> tuple[list[dict], list[dict]]:
    """Post one messaging event. Returns (nudge calls, messages) it caused."""
    fired_before, sent_before = len(FIRED), len(SENT)
    body = {"object": "instagram", "entry": [{"id": "biz", "time": 1, "messaging": [
        {"recipient": {"id": "biz"}, "timestamp": 1, **event}
    ]}]}
    response = client.post("/instagram/webhook", json=body)
    assert response.status_code == 200, response.text
    return FIRED[fired_before:], SENT[sent_before:]


def message(sender: str, text: str = "", **extra) -> dict:
    body = {"mid": f"m_{len(FIRED)}_{len(SENT)}"}
    if text:
        body["text"] = text
    body.update(extra)
    return {"sender": {"id": sender}, "message": body}


def postback(sender: str, payload: str = "", title: str = "") -> dict:
    body = {"mid": "pb", "title": title}
    if payload:
        body["payload"] = payload
    return {"sender": {"id": sender}, "postback": body}


def outcomes(sender: str) -> list[str]:
    with get_connection() as c:
        return [r[0] for r in c.execute(
            "SELECT outcome FROM instagram_webhook_events WHERE sender_id = ? ORDER BY id", (sender,)
        )]


def user_row(sender: str) -> dict:
    with get_connection() as c:
        row = c.execute("SELECT * FROM users WHERE instagram_user_id = ?", (sender,)).fetchone()
    return dict(row) if row else {}


def main() -> None:
    with TestClient(app) as client:
        # --- taps and typed text are left for a person ----------------------
        fired, sent = deliver(client, postback("tap_how", "ICE_HOW", "How do I save a reel here?"))
        check("an ice breaker tap gets no bot reply", fired == [] and sent == [], str(sent))
        check("an ice breaker tap is flagged for Shlok", "needs_human" in outcomes("tap_how"), str(outcomes("tap_how")))
        check("the tap is still counted", "tap:ICE_HOW" in outcomes("tap_how"), str(outcomes("tap_how")))
        fired, sent = deliver(client, message("tap_chip", "What does it do", quick_reply={"payload": "ICE_WHAT"}))
        check("a tapped chip gets no bot reply and is flagged", sent == [] and "needs_human" in outcomes("tap_chip"), str(outcomes("tap_chip")))
        check("a tapped chip is not read as a reel message", "ignored" not in outcomes("tap_chip"), str(outcomes("tap_chip")))

        # --- a heart is not a message --------------------------------------
        deliver(client, message("heart", "hi"))
        before = user_row("heart")["last_inbound_at"]
        fired, sent = deliver(client, {"sender": {"id": "heart"}, "reaction": {"mid": "x", "action": "react", "emoji": "❤"}})
        check("a reaction gets no reply", fired == [] and sent == [], str(fired))
        check("a reaction is logged as ignored", "ignored_reaction" in outcomes("heart"), str(outcomes("heart")))
        check("a reaction does not reopen the reply window", user_row("heart")["last_inbound_at"] == before)
        fired, sent = deliver(client, {"sender": {"id": "heart"}, "read": {"mid": "x"}})
        check("a read receipt gets no reply", fired == [] and sent == [])

        # --- typed text -----------------------------------------------------
        for sender, text in (("typed_a", "hi"), ("typed_b", "how do i save one?"), ("typed_c", "Is it free?"), ("typed_d", "\U0001F44B")):
            fired, sent = deliver(client, message(sender, text))
            check(f"typed {text!r} gets no bot reply", fired == [] and sent == [], str(sent))
            check(f"typed {text!r} is flagged for Shlok", "needs_human" in outcomes(sender), str(outcomes(sender)))
        with get_connection() as c:
            stored = c.execute("SELECT detail FROM instagram_webhook_events WHERE outcome = 'needs_human' AND sender_id = 'typed_b'").fetchone()[0]
        check("what they wrote is not stored", "save" not in stored, stored)
        fired, sent = deliver(client, message("voice", attachments=[{"type": "audio", "payload": {"url": "https://lookaside.fbsbx.com/a"}}]))
        check("a voice note gets no bot reply and is flagged", sent == [] and "needs_human" in outcomes("voice"), str(outcomes("voice")))
        fired, sent = deliver(client, message("story", attachments=[{"type": "story_mention", "payload": {"url": "https://lookaside.fbsbx.com/s"}}]))
        check("a story mention gets no bot reply and is flagged", sent == [] and "needs_human" in outcomes("story"), str(outcomes("story")))
        fired, sent = deliver(client, message("unsender", is_deleted=True))
        check("an unsent message is neither answered nor flagged", sent == [] and "needs_human" not in outcomes("unsender"), str(outcomes("unsender")))

        # --- delete my data ------------------------------------------------
        fired, sent = deliver(client, message("deleter", "Delete my data"))
        check("delete my data reaches the delete acknowledgement", [f["trigger"] for f in fired] == ["delete_request"], str(fired))
        check("delete my data is also flagged for Shlok", "needs_human" in outcomes("deleter"), str(outcomes("deleter")))
        check("the acknowledgement says 7 days", sent and "within 7 days" in sent[0]["text"], str(sent))
        check("the request is logged", "delete_requested" in outcomes("deleter"), str(outcomes("deleter")))
        fired, sent = deliver(client, postback("deleter_menu", "MENU_DELETE", "Delete my data"))
        check("the delete menu item is logged too", "delete_requested" in outcomes("deleter_menu") and len(sent) == 1, str(sent))
        fired, sent = deliver(client, message("not_deleter", "can you delete this reel"))
        check("an ordinary sentence with delete in it is not a request", "delete_requested" not in outcomes("not_deleter"))

        for i in range(260):  # the log keeps only its newest 200 rows
            route._log_webhook_event("filler", sender_id="filler", outcome="noise", detail=str(i))
        check("a delete request survives the log being trimmed", "delete_requested" in outcomes("deleter"))
        check("a waiting message survives the log being trimmed", "needs_human" in outcomes("typed_a"))

        from app.api.routes.health import _instagram_webhook_debug

        listed = _instagram_webhook_debug().get("delete_requests") or []
        check("the health page lists the delete requests", {r["sender"] for r in listed} == {"deleter", "deleter_menu"}, str(listed))
        check("each listed request names the account", all(r["user_id"] == user_row(r["sender"])["id"] for r in listed), str(listed))
        waiting = _instagram_webhook_debug().get("human_messages") or {}
        people = {p["sender"] for p in waiting.get("people", [])}
        check("the health page counts the waiting messages", waiting.get("last_24h", 0) >= 9 and {"typed_a", "typed_b", "tap_how", "voice"} <= people, str(waiting)[:300])
        check("the health page shows no message text", "how do i save" not in str(waiting).lower())

        # --- reels ---------------------------------------------------------
        url = "https://www.instagram.com/reel/ABC123xyz/?igsh=abc"
        fired, sent = deliver(client, message("saver", url))
        check("a first reel gets the instant acknowledgement", [f["trigger"] for f in fired] == ["reel_saved"] and sent and sent[0]["text"].startswith("Got it."), str(sent))
        check("the acknowledgement has no button", sent and sent[0]["format"] == "text")

        saver = user_row("saver")
        with get_connection() as c:
            reel_id = c.execute("SELECT id FROM reels WHERE user_id = ?", (saver["id"],)).fetchone()[0]
            c.execute("UPDATE reels SET status = 'completed' WHERE id = ?", (reel_id,))
            c.execute("INSERT INTO reel_items (reel_id, item_name, created_at) VALUES (?, 'Banaras Cafe', '2026-10-12')", (reel_id,))
        nudge.fire(saver["id"], "reel_ready", "Banaras Cafe")
        first_library = SENT[-1]
        check("the first library message is a button, not a pasted link", first_library["format"] == "button" and first_library["labels"] == ["Open my library"] and "http" not in first_library["text"], str(first_library))
        check("the first library message quotes no title", "Banaras" not in first_library["text"], str(first_library))
        check("the button opens their own link", first_library["urls"][0] == f"https://clipnest.in/g/{user_row('saver')['library_token']}", str(first_library))

        fired, sent = deliver(client, message("saver", "https://www.instagram.com/reel/ABC123xyz/"))
        check("a duplicate reel reaches the already saved reply", [f["trigger"] for f in fired] == ["already_saved"], str(fired))
        check("the already saved reply quotes no title", sent and sent[0]["text"] == "You already have that one. It is in your library.", str(sent))
        with get_connection() as c:
            jobs = c.execute("SELECT COUNT(*) FROM processing_jobs WHERE user_id = ?", (saver["id"],)).fetchone()[0]
        check("a duplicate reel queues no second read", jobs == 1, f"jobs={jobs}")

        with get_connection() as c:
            c.execute("UPDATE users SET last_dm_at = '' WHERE instagram_user_id = 'saver'")
        fired, sent = deliver(client, message("saver", attachments=[{"type": "ig_reel", "payload": {"reel_video_id": "5"}}]))
        check("a reel share with no link reaches the unreadable share reply", [f["trigger"] for f in fired] == ["unreadable_share"], str(fired))
        check("the unreadable share reply explains Copy link", sent and "Copy link" in sent[0]["text"] and sent[0]["labels"] == [], str(sent))

        for kind in ("share", "ig_post", "image"):
            fired, sent = deliver(client, message(f"post_{kind}", attachments=[{"type": kind, "payload": {"url": "https://lookaside.fbsbx.com/x"}}]))
            check(f"a shared {kind} is told reels only", [f["trigger"] for f in fired] == ["photo_post"] and sent and sent[0]["text"].startswith("I only save reels for now, not posts"), str(sent))
        fired, sent = deliver(client, message("reel_no_link", attachments=[{"type": "ig_reel", "payload": {"reel_video_id": "9"}}]))
        check("a shared reel with no link still gets the copy link reply", [f["trigger"] for f in fired] == ["unreadable_share"], str(fired))

        fired, sent = deliver(client, message("poster", "https://www.instagram.com/p/POST12345/"))
        check("a /p/ link is still saved, not refused", [f["trigger"] for f in fired] == ["reel_saved"] and "saved" in outcomes("poster"), str(fired))

        fired, sent = deliver(client, message("native", attachments=[{"type": "ig_reel", "payload": {"reel_video_id": "1", "title": "x", "url": "https://www.instagram.com/reel/NATIVE777/"}}]))
        check("a native share with a permalink is saved", "saved" in outcomes("native"), str(outcomes("native")))

        # --- signed in users stay untouched --------------------------------
        deliver(client, message("member", "https://www.instagram.com/reel/MEMBER111/"))
        with get_connection() as c:
            c.execute("UPDATE users SET google_sub = 'g_member' WHERE instagram_user_id = 'member'")
        fired, sent = deliver(client, message("member", "hello"))
        check("a signed in user typing hello hears nothing and is flagged", sent == [] and "needs_human" in outcomes("member"), str(sent))
        fired, sent = deliver(client, message("member", "delete my data"))
        check("a signed in user asking to delete is acknowledged", len(sent) == 1 and sent[0]["text"] == "Got it. Your data will be deleted within 7 days.", str(sent))
        member = user_row("member")
        with get_connection() as c:
            c.execute("UPDATE reels SET status = 'completed' WHERE user_id = ?", (member["id"],))
            c.execute("UPDATE users SET last_dm_at = '' WHERE id = ?", (member["id"],))
        before = len(SENT)
        nudge.fire(member["id"], "reel_failed")
        check("a signed in user is told when a reel fails", len(SENT) == before + 1 and SENT[-1]["text"].startswith("I could not read that one"), str(SENT[before:]))

        # --- coming back after a week ----------------------------------------
        deliver(client, message("returner", "https://www.instagram.com/reel/OLD11111/"))
        deliver(client, message("returner", "https://www.instagram.com/reel/OLD22222/"))
        with get_connection() as c:
            c.execute("UPDATE reels SET received_at = '2026-09-01T10:00:00' WHERE user_id = ?", (user_row("returner")["id"],))
            c.execute("UPDATE users SET last_dm_at = '' WHERE instagram_user_id = 'returner'")
        fired, sent = deliver(client, message("returner", "https://www.instagram.com/reel/NEW33333/ https://www.instagram.com/reel/NEW44444/"))
        check("a guest back after a week is welcomed back", [f["trigger"] for f in fired] == ["reel_returned"] and sent and sent[0]["text"] == "Saved. Your library is where you left it." and sent[0]["labels"] == ["Open my library"], str(sent))
        with get_connection() as c:
            c.execute("UPDATE users SET last_dm_at = '' WHERE instagram_user_id = 'returner'")
        fired, sent = deliver(client, message("returner", "https://www.instagram.com/reel/NEW55555/"))
        check("the next reel straight after is silent again", [f["trigger"] for f in fired] == ["reel_saved"] and sent == [], str(sent))

        # --- the library page ----------------------------------------------
        token = user_row("saver")["library_token"]
        page = client.get(f"/g/{token}")
        check("the library page opens", page.status_code == 200)
        check("a pasted library link is titled", '<meta property="og:title" content="Your ClipNest library" />' in page.text)
        check("and says how many reels", 'content="1 saved reel, searchable in plain words."' in page.text)
        check("the library page shows no home screen card at 1 reel", '"claimStage": ""' in page.text)
        prompted = client.get(f"/g/{token}?hs=prompt")
        check("the 5 reel button opens the home screen card", '"claimStage": "home"' in prompted.text)
        landing = client.get("/")
        check("the landing page keeps its own title", '<meta property="og:title" content="ClipNest" />' in landing.text)

        # --- the old text switch -------------------------------------------
        object.__setattr__(nudge.settings, "dm_rich_messages", False)
        fired, sent = deliver(client, message("plain_mode", "https://www.instagram.com/reel/PLAIN999/"))
        plain = user_row("plain_mode")
        with get_connection() as c:
            c.execute("UPDATE reels SET status = 'completed' WHERE user_id = ?", (plain["id"],))
        before = len(SENT)
        nudge.fire(plain["id"], "reel_ready", "Goa Hostel")
        check("with DM_RICH_MESSAGES=0 the first library message is plain text with the link", SENT[before]["format"] == "text" and "Here is your library: https://clipnest.in/g/" in SENT[before]["text"], str(SENT[before]))
        object.__setattr__(nudge.settings, "dm_rich_messages", True)

    for sent in SENT:
        for issue in nudge.copy_problems(sent["text"]) + [i for label in sent["labels"] for i in nudge.copy_problems(label)]:
            check("copy rules", False, f"{issue}: {sent['text']}")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} of {CHECKS} checks FAILED")
        sys.exit(1)
    print(f"all {CHECKS} checks passed")


if __name__ == "__main__":
    main()
