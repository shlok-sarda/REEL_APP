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
import re
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
os.environ["INSTAGRAM_APP_USERNAME"] = "clipnest.in"

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
# A preview waits a few seconds before it is answered; here the wait is
# skipped unless a test holds it to deliver something in between.
HELD: list = []
HOLD = {"on": False}


def _settle(func, *args):
    if HOLD["on"]:
        HELD.append((func, args))
    else:
        func(*args)


def release_held() -> None:
    HOLD["on"] = False
    while HELD:
        func, args = HELD.pop(0)
        func(*args)


route._settle_then = _settle
# Our own reels, as the Graph API would list them. No network in tests.
OWN_IDS = {"17900000000000001"}
OWN_CODES = {"ADREEL0001", "OURPOST01"}
route.own_media._known = lambda: (OWN_IDS, OWN_CODES)
route.own_media._cache["by_id"] = {"17900000000000001": "ADREEL0001"}
route.own_media._look_up = lambda media_id: ""
# The ad's reel, for an ad visit that names no reel (a bare picture).
route.own_media.OWN_REEL_URLS[:] = ["https://www.instagram.com/reel/ADREEL0001/"]

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


def deliver_many(client: TestClient, events: list[dict]) -> tuple[list[dict], list[dict]]:
    """Several messaging events in one delivery, as Instagram batches them."""
    fired_before, sent_before = len(FIRED), len(SENT)
    body = {"object": "instagram", "entry": [{"id": "biz", "time": 1, "messaging": [
        {"recipient": {"id": "biz"}, "timestamp": 1, **event} for event in events
    ]}]}
    response = client.post("/instagram/webhook", json=body)
    assert response.status_code == 200, response.text
    return FIRED[fired_before:], SENT[sent_before:]


# The referral block Meta documents for a chat opened from an ad (click to
# Instagram Direct). Values are made up; the keys are Meta's.
AD_REFERRAL = {
    "ref": "",
    "ad_id": "120200000000000001",
    "source": "ADS",
    "type": "OPEN_THREAD",
    "ads_context_data": {
        "ad_title": "Save reels in one tap",
        "photo_url": "https://scontent.cdninstagram.com/v/ad_thumb.jpg",
        "video_url": "https://scontent.cdninstagram.com/v/ad_video.mp4",
        "post_id": "17900000000000001",
    },
}
# The ad's reel as Instagram may attach it to the chat ("sent you a post").
AD_PREVIEW_POST = {"type": "ig_post", "payload": {"url": "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=1", "title": "Save reels in one tap", "ig_post_media_id": "17900000000000001"}}
AD_PREVIEW_SHARE = {"type": "share", "payload": {"url": "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=2"}}
AD_PREVIEW_REEL = {"type": "ig_reel", "payload": {"reel_video_id": "17900000000000001", "title": "Save reels in one tap", "url": "https://www.instagram.com/reel/ADREEL0001/"}}


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


def details(sender: str) -> list[str]:
    with get_connection() as connection:
        return [r[0] for r in connection.execute(
            "SELECT detail FROM instagram_webhook_events WHERE sender_id = ? ORDER BY id", (sender,)
        )]


def user_row(sender: str) -> dict:
    with get_connection() as c:
        row = c.execute("SELECT * FROM users WHERE instagram_user_id = ?", (sender,)).fetchone()
    return dict(row) if row else {}


def _counter_rows(sender: str) -> list[tuple]:
    with get_connection() as c:
        return [tuple(r) for r in c.execute("SELECT outcome, reason FROM reel_receipts WHERE sender_id = ?", (sender,))]


AD_ANSWER_TEXT = "Send any reel to this chat and I save it for you."
AGAIN_TEXT = "To save a reel, open it, tap share, pick @clipnest.in and send it to me."


def main() -> None:
    with TestClient(app) as client:
        # --- taps and typed text are told how it works (2026-10-23) ---------
        fired, sent = deliver(client, postback("tap_how", "ICE_HOW", "Can you show examples?"))
        check("an ice breaker tap gets the how it works reply", len(sent) == 1 and sent[0]["text"].startswith(AD_ANSWER_TEXT), str(sent))
        check("an ice breaker tap is flagged for Shlok", "needs_human" in outcomes("tap_how"), str(outcomes("tap_how")))
        check("the tap is still counted", "tap:ICE_HOW" in outcomes("tap_how"), str(outcomes("tap_how")))
        fired, sent = deliver(client, message("tap_chip", "What does it do", quick_reply={"payload": "ICE_WHAT"}))
        check("a tapped chip gets the how it works reply and is flagged", len(sent) == 1 and sent[0]["text"].startswith(AD_ANSWER_TEXT) and "needs_human" in outcomes("tap_chip"), str(sent))
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
        for sender, text in (("typed_a", "hi"), ("typed_b", "how do i save one?"), ("typed_c", "Save this to recepie"), ("typed_d", "\U0001F44B")):
            fired, sent = deliver(client, message(sender, text))
            check(f"typed {text!r} gets the how it works reply", len(sent) == 1 and sent[0]["text"].startswith(AD_ANSWER_TEXT), str(sent))
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
        check("their words survive the log being trimmed", "said" in outcomes("typed_a"))

        # --- the Messages tab: what people wrote, word for word -------------
        from app.services.dm_messages import recent_messages
        from app.ui_ux.admin_dashboard import render_messages

        check("typed words are kept word for word", any(d and d not in ("text",) and "said" == o for d, o in zip(details("typed_a"), outcomes("typed_a"))), str(details("typed_a")))
        check("a tapped question is kept as a tap", any(d.startswith("Tapped: ") for d in details("tap_how")), str(details("tap_how")))
        check("a voice note is noted", "[voice note]" in details("voice"), str(details("voice")))
        with get_connection() as c:
            dm = recent_messages(c, show_all=True)
        senders = {p["sender_id"] for p in dm["people"]}
        check("the Messages tab lists who wrote", {"typed_a", "tap_how", "voice"} <= senders, str(senders)[:300])
        check("a shared reel is not listed as a message", not any("instagram.com/reel/" in m["words"] for p in dm["people"] for m in p["messages"] if not p["sender_id"].startswith("typed")), "")
        page = render_messages(dm)
        check("the Messages tab renders the words", "Tapped: Can you show examples?" in page and "Messages" in page, page[:200])

        # --- hand replies: echoes the bot did not send ----------------------
        from app.services import dm_outgoing

        dm_outgoing.note_bot_send("typed_a", {"message": {"text": "bot line"}}, '{"recipient_id": "typed_a", "message_id": "mid_bot_1"}')
        deliver(client, {"sender": {"id": "biz"}, "recipient": {"id": "typed_a"}, "message": {"mid": "mid_bot_1", "is_echo": True, "text": "bot line"}})
        fired, sent = deliver(client, {"sender": {"id": "biz"}, "recipient": {"id": "typed_a"}, "message": {"mid": "mid_hand_1", "is_echo": True, "text": "Thanks, will do"}})
        check("an echo is not answered as a message", sent == [] and fired == [], str(sent))
        dm_outgoing.note_bot_send("tap_how", {"message": {"text": "late note"}}, '{"message_id": "mid_bot_2"}')
        deliver(client, {"sender": {"id": "biz"}, "recipient": {"id": "tap_how"}, "message": {"mid": "mid_bot_2", "is_echo": True, "text": "late note"}})
        with get_connection() as c:
            out = {r["mid"]: dict(r) for r in c.execute("SELECT * FROM dm_outgoing")}
        check("the bot's own send is marked as the bot", out.get("mid_bot_1", {}).get("by_bot") == 1, str(out))
        check("an echo the bot never sent is a hand reply", out.get("mid_hand_1", {}).get("by_bot") == 0 and out["mid_hand_1"]["recipient_id"] == "typed_a" and out["mid_hand_1"]["words"] == "Thanks, will do", str(out))
        check("the bot's send is recognised whichever lands first", out.get("mid_bot_2", {}).get("by_bot") == 1 and out["mid_bot_2"]["echoed"] == 1, str(out))

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
            check(f"a shared {kind} is told how to send the reel link", [f["trigger"] for f in fired] == ["photo_post"] and sent and sent[0]["text"].startswith("Instagram did not send me the link for that one."), str(sent))
        fired, sent = deliver(client, message("reel_no_link", attachments=[{"type": "ig_reel", "payload": {"reel_video_id": "9"}}]))
        check("a shared reel with no link still gets the copy link reply", [f["trigger"] for f in fired] == ["unreadable_share"], str(fired))

        fired, sent = deliver(client, message("poster", "https://www.instagram.com/p/POST12345/"))
        check("a /p/ link is still saved, not refused", [f["trigger"] for f in fired] == ["post_saved"] and "saved" in outcomes("poster"), str(fired))
        check("and is never called a reel", sent and "reel" not in sent[0]["text"].lower() and "post" in sent[0]["text"], str(sent))

        # --- Anay, 2026-10-18: a photo post shared, then its link pasted ----
        # The exact shape production logged for his share.
        photo_share = {"type": "ig_post", "payload": {"ig_post_media_id": "17966985714191050", "title": "mentalistaaaaa Publicacao 120", "url": "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=1"}}
        fired, sent = deliver(client, message("anay", attachments=[photo_share]))
        check("his shared photo gets the copy link line", [f["trigger"] for f in fired] == ["photo_post"] and sent and "reel or a video" in sent[0]["text"] and "cannot save photos" in sent[0]["text"], str(sent))
        fired, sent = deliver(client, message("anay", "https://www.instagram.com/p/DeLHyr-B_Di/?rpxt=MW1ncXdsY2xydG1jaQ=="))
        check("the pasted photo link is not called a reel", [f["trigger"] for f in fired] == ["post_saved"] and sent and "reel" not in sent[0]["text"].lower(), str(sent))
        from app.workers import process_queue
        with get_connection() as c:
            job = dict(c.execute("SELECT * FROM processing_jobs WHERE user_id = ? ORDER BY rowid DESC LIMIT 1", (user_row("anay")["id"],)).fetchone())
        before = len(SENT)
        process_queue.fail_job = lambda *a, **k: None
        process_queue.fail_reel_job(job, "Processing error: Reel unavailable: no video, caption, or transcript could be fetched", None)
        check("and when it turns out a photo, he is told so", len(SENT) == before + 1 and SENT[-1]["text"].startswith("I could not save that post. It is most likely a photo"), str(SENT[before:]))
        fired, sent = deliver(client, message("unsupported", attachments=[{"type": "unsupported_type", "payload": {"url": "https://lookaside.fbsbx.com/x"}}]))
        check("a share Instagram will not describe gets the copy link reply", [f["trigger"] for f in fired] == ["unreadable_share"] and sent and "Copy link" in sent[0]["text"], str(sent))
        fired, sent = deliver(client, message("mixed", "https://www.instagram.com/p/MIXP1111/ https://www.instagram.com/reel/MIXR2222/"))
        check("a reel next to a post link is still treated as a reel", [f["trigger"] for f in fired] == ["reel_saved"], str(fired))

        fired, sent = deliver(client, message("native", attachments=[{"type": "ig_reel", "payload": {"reel_video_id": "1", "title": "x", "url": "https://www.instagram.com/reel/NATIVE777/"}}]))
        check("a native share with a permalink is saved", "saved" in outcomes("native"), str(outcomes("native")))

        fired, sent = deliver(client, message("post_note", "is this one saved?", attachments=[{"type": "ig_post", "payload": {"url": "https://lookaside.fbsbx.com/x"}}]))
        check("a post sent with their own words is told how it works, not reels only", len(sent) == 1 and sent[0]["text"].startswith(AD_ANSWER_TEXT) and "needs_human" in outcomes("post_note"), str(sent))

        # --- opened from an ad ---------------------------------------------
        def reels_of(sender: str) -> int:
            row = user_row(sender)
            if not row:
                return 0
            with get_connection() as c:
                return c.execute("SELECT COUNT(*) FROM reels WHERE user_id = ?", (row["id"],)).fetchone()[0]

        AD_ANSWER = "Send any reel to this chat and I save it for you."
        HOW_ANSWER = "You send me a reel and I save it for you."
        FREE_ANSWER = "Yes, it is free. No app and no sign up to start."
        SHARE_ANSWER = "Open the reel, tap the share arrow"
        for name, preview in (("ad_post", AD_PREVIEW_POST), ("ad_share", AD_PREVIEW_SHARE), ("ad_reel", AD_PREVIEW_REEL)):
            fired, sent = deliver(client, message(name, "How does this work?", referral=AD_REFERRAL, attachments=[preview]))
            check(f"an ad message with a {preview['type']} preview gets the answer to its question", [f["trigger"] for f in fired] == ["ad_q_how"] and len(sent) == 1 and sent[0]["text"].startswith(HOW_ANSWER), str(sent))
            check(f"an ad message with a {preview['type']} preview is never told reels only", not any("not posts" in s["text"] for s in sent), str(sent))
            check(f"an ad message with a {preview['type']} preview saves our reel once", reels_of(name) == 1 and "own_saved" in outcomes(name), str(outcomes(name)))
            check(f"an ad message with a {preview['type']} preview logs its shape", "ad_referral" in outcomes(name), str(outcomes(name)))
            check(f"an answered ad message is not left waiting for Shlok", "needs_human" not in outcomes(name), str(outcomes(name)))
        with get_connection() as c:
            shape = c.execute("SELECT detail FROM instagram_webhook_events WHERE sender_id = 'ad_post' AND outcome = 'ad_referral'").fetchone()[0]
        check("the logged ad shape keeps no text, ad id or link", "How does" not in shape and "120200000000000001" not in shape and "http" not in shape and "source=ADS" in shape, shape)

        fired, sent = deliver(client, message("ad_post", "Is it really free?", referral=AD_REFERRAL))
        check("a second ad question gets its own answer", len(sent) == 1 and sent[0]["text"].startswith(FREE_ANSWER), str(sent))
        check("is it really free starts with yes", sent and sent[0]["text"].startswith("Yes, it is free."), str(sent))
        fired, sent = deliver(client, message("ad_post", "Is it really free?", referral=AD_REFERRAL))
        check("the same ad question twice gets the short how line, not its answer again", len(sent) == 1 and sent[0]["text"].startswith(AGAIN_TEXT) and "needs_human" in outcomes("ad_post"), str(sent))

        fired, sent = deliver(client, message("ad_quiet", referral=AD_REFERRAL, attachments=[AD_PREVIEW_POST]))
        check("an ad preview with no words saves the ad and says so, with their library", len(sent) == 1 and sent[0]["text"].startswith("Saved that reel to your library.") and sent[0]["labels"] == ["Open my library"], str(sent))

        fired, sent = deliver_many(client, [
            message("ad_split", attachments=[AD_PREVIEW_REEL]),
            message("ad_split", "How does this work?", referral=AD_REFERRAL),
        ])
        check("an ad preview split from the referral in one delivery gets one answer", len(sent) == 1 and sent[0]["text"].startswith(HOW_ANSWER), str(sent))
        check("an ad preview split from the referral saves our reel once", reels_of("ad_split") == 1, str(outcomes("ad_split")))

        fired, sent = deliver(client, {"sender": {"id": "ad_tap"}, "postback": {"mid": "pb", "title": "How does it work?", "payload": "AD_Q"}, "referral": AD_REFERRAL})
        check("a tapped ad question gets its answer", len(sent) == 1 and sent[0]["text"].startswith(HOW_ANSWER), str(sent))

        fired, sent = deliver(client, message("ad_post", attachments=[{"type": "ig_reel", "payload": {"reel_video_id": "555", "url": "https://www.instagram.com/reel/THEIRREEL1/"}}]))
        check("a reel they share after the ad chat goes through the normal flow", [f["trigger"] for f in fired] == ["reel_saved"] and reels_of("ad_post") == 2, str(fired))

        deliver(client, message("ad_member", "https://www.instagram.com/reel/ADMEMBER1/"))
        with get_connection() as c:
            c.execute("UPDATE users SET google_sub = 'g_ad_member', last_dm_at = '' WHERE instagram_user_id = 'ad_member'")
        fired, sent = deliver(client, message("ad_member", "How does this work?", referral=AD_REFERRAL))
        check("a signed in person who taps the ad gets the answer too", len(sent) == 1 and sent[0]["text"].startswith(HOW_ANSWER), str(sent))

        # --- ad layouts seen on 16 and 17 Oct ---------------------------------
        AD_PICTURE = {"type": "image", "payload": {"url": "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=9"}}

        def no_posts_line(items):
            return not any("not posts" in s["text"] for s in items)

        fired, sent = deliver(client, {"sender": {"id": "pb_ref"}, "postback": {"mid": "pb2", "title": "Is it really free?", "payload": "AD_Q2", "referral": AD_REFERRAL}})
        check("a tapped question with the referral inside the tap gets its answer", len(sent) == 1 and sent[0]["text"].startswith(FREE_ANSWER), str(sent))
        check("that tap is not left waiting for Shlok", "needs_human" not in outcomes("pb_ref"), str(outcomes("pb_ref")))

        def keys_sent(sender: str) -> list[str]:
            with get_connection() as c:
                return [r[0] for r in c.execute("SELECT message_key FROM nudge_log WHERE user_id = ? ORDER BY id", (user_row(sender)["id"],))]

        HOLD["on"] = True
        before = len(SENT)
        deliver(client, {"sender": {"id": "ref_only"}, "referral": AD_REFERRAL})
        deliver(client, message("ref_only", "How does it work?"))
        release_held()
        check("a referral with no message is not dropped", "ad_referral" in outcomes("ref_only"), str(outcomes("ref_only")))
        check("a referral then its question in another delivery get one reply", len(SENT) == before + 1 and SENT[-1]["text"].startswith(HOW_ANSWER), str(SENT[before:]))
        check("and nothing more after the wait", keys_sent("ref_only") == ["m25_ad_how"], str(keys_sent("ref_only")))

        HOLD["on"] = True
        deliver(client, {"sender": {"id": "ref_alone"}, "referral": AD_REFERRAL})
        before = len(SENT)
        release_held()
        check("a referral alone saves the ad and says so after the wait", len(SENT) == before + 1 and SENT[-1]["text"].startswith("Saved that reel to your library."), str(SENT[before:]))

        HOLD["on"] = True
        before = len(SENT)
        deliver(client, message("pic_first", attachments=[AD_PICTURE]))
        deliver(client, message("pic_first", "How does it work?", referral=AD_REFERRAL))
        release_held()
        check("the ad as a picture, then the question: one answer", len(SENT) == before + 1 and SENT[-1]["text"].startswith(HOW_ANSWER), str(SENT[before:]))
        check("the ad as a picture is never told reels only", no_posts_line(SENT[before:]), str(SENT[before:]))
        check("the ad as a picture saves our reel once", reels_of("pic_first") == 1, str(outcomes("pic_first")))

        before = len(SENT)
        deliver(client, message("pic_after", "Is it really free?", referral=AD_REFERRAL))
        deliver(client, message("pic_after", attachments=[AD_PICTURE]))
        deliver(client, message("pic_after", "Is it really free?", referral=AD_REFERRAL, attachments=[AD_PICTURE]))
        check("question, then the ad picture, then the same again: the answer once, then the short how line", [m["text"][:20] for m in SENT[before:]] == [FREE_ANSWER[:20], AGAIN_TEXT[:20]], str(SENT[before:]))
        check("the ad picture after the answer is marked as the ad preview", "ad_preview_ignored" in outcomes("pic_after"), str(outcomes("pic_after")))

        before = len(SENT)
        deliver(client, message("pic_q", "How does it work?", attachments=[AD_PICTURE]))
        check("the ad picture with a question and no referral gets the answer", len(SENT) == before + 1 and SENT[-1]["text"].startswith(HOW_ANSWER), str(SENT[before:]))

        # --- Meta's ad tap questions with no ad click logged (2026-10-23) -----
        before = len(SENT)
        deliver(client, postback("meta_q", "META_Q", "What's your process for saving and sharing recommendations?"))
        deliver(client, message("meta_q", attachments=[{"type": "ig_post", "payload": {"ig_post_media_id": "3799999999999999999", "url": "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=9"}}]))
        check("a Meta ad question tap with no ad click gets the how it works reply", len(SENT) == before + 1 and SENT[before]["text"].startswith(AD_ANSWER_TEXT), str(SENT[before:]))
        check("the ad preview after it gets no photo line", no_posts_line(SENT[before:]) and not any(m["text"].startswith("Instagram did not send me the link") for m in SENT[before:]), str(SENT[before:]))
        check("the ad preview after it is not counted as a post with no link", "no_link_post" not in str(_counter_rows("meta_q")), str(_counter_rows("meta_q")))
        before = len(SENT)
        deliver(client, message("meta_q", "What's the next step?"))
        check("what's the next step gets the short how line", len(SENT) == before + 1 and SENT[-1]["text"].startswith(AGAIN_TEXT), str(SENT[before:]))
        before = len(SENT)
        deliver(client, message("meta_typed", "What's your process for saving and sharing recommendations?"))
        deliver(client, message("meta_typed", attachments=[AD_PICTURE]))
        check("the same question typed, then the preview: one reply, no photo line", len(SENT) == before + 1 and SENT[before]["text"].startswith(AD_ANSWER_TEXT), str(SENT[before:]))

        # --- a reel shared after the ad answer is theirs (2026-10-17) ---------
        FEED_REEL = {"type": "ig_post", "payload": {"ig_post_media_id": "3712345678901234567", "title": "x", "url": "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=7"}}
        deliver(client, postback("after_ad", "AD_Q1", "How does it work?"))
        # A person needs more than a few seconds to read that and share a reel.
        with get_connection() as c:
            c.execute(
                "UPDATE nudge_log SET sent_at = ? WHERE user_id = ?",
                (route._since(route.PREVIEW_AFTER_ANSWER_SECONDS + 15), user_row("after_ad")["id"]),
            )
        before = len(SENT)
        deliver(client, message("after_ad", attachments=[FEED_REEL]))
        check("a reel shared right after an ad answer is not dropped as the ad", "ad_preview_ignored" not in outcomes("after_ad"), str(outcomes("after_ad")))
        check("and it gets a reply", len(SENT) == before + 1 and "Copy link" in SENT[-1]["text"], str(SENT[before:]))
        before = len(SENT)
        deliver(client, message("after_ad", attachments=[FEED_REEL]))
        check("a second one inside the cooldown is answered too", len(SENT) == before + 1, str(SENT[before:]))
        check("the post id is kept in the log for checking", any("media_ids=['3712345678901234567']" in r for r in details("after_ad")), str(details("after_ad")))

        deliver(client, message("ref_then_reel", "Is it really free?", referral=AD_REFERRAL))
        with get_connection() as c:
            c.execute(
                "UPDATE instagram_webhook_events SET received_at = ? WHERE sender_id = 'ref_then_reel' AND outcome = 'ad_referral'",
                (route._since(route.AD_PREVIEW_SECONDS + 30),),
            )
            c.execute(
                "UPDATE nudge_log SET sent_at = ? WHERE user_id = ?",
                (route._since(route.AD_PREVIEW_SECONDS + 30), user_row("ref_then_reel")["id"]),
            )
        before = len(SENT)
        deliver(client, message("ref_then_reel", attachments=[FEED_REEL]))
        check("a reel a minute after opening from the ad gets a reply", len(SENT) == before + 1 and "Copy link" in SENT[-1]["text"], str(SENT[before:]))

        failer = user_row("after_ad")["id"]
        before = len(SENT)
        nudge.fire(failer, "reel_failed_ours")
        nudge.fire(failer, "reel_failed_ours")
        check("a reel that broke on our side is not blamed on the reel", len(SENT) == before + 2 and "not yours" in SENT[-1]["text"] and "rivate" not in SENT[-1]["text"], str(SENT[before:]))

        # Pick test senders that land in each group, by the same fixed hash.
        egg_ids = [f"egg_{i}" for i in range(200) if nudge.own_reel_group(f"egg_{i}") == "egg"]
        plain_ids = [f"plain_{i}" for i in range(200) if nudge.own_reel_group(f"plain_{i}") == "plain"]
        share_rate = len([i for i in range(1000) if nudge.own_reel_group(f"rate_{i}") == "egg"]) / 1000
        check("about one in five land in the Easter egg group", 0.15 <= share_rate <= 0.25, str(share_rate))
        check("the group never changes for a person", all(nudge.own_reel_group(egg_ids[0]) == "egg" for _ in range(5)))
        own_reel = {"type": "ig_reel", "payload": {"reel_video_id": "1", "url": "https://www.instagram.com/reel/OURPOST01/"}}
        egg = egg_ids[0]
        before = len(SENT)
        deliver(client, message(egg, attachments=[own_reel]))
        check("the Easter egg group gets the Easter egg", len(SENT) == before + 1 and SENT[-1]["text"].startswith("You found our reel, so I saved it to your library. Easter egg unlocked: you can save up to 100 reels a month free, double the usual."), str(SENT[before:]))
        check("with the library button", SENT[-1]["labels"] == ["Open my library"], str(SENT[-1]))
        check("and their monthly cap is now 100", nudge.monthly_cap_for(user_row(egg)["id"]) == 100 and user_row(egg)["own_reel_group"] == "egg", str(user_row(egg).get("monthly_cap_override")))
        check("the egg reel is saved", reels_of(egg) == 1)
        plain = plain_ids[0]
        deliver(client, message(plain, attachments=[own_reel]))
        check("the plain group keeps the usual cap and is logged", nudge.monthly_cap_for(user_row(plain)["id"]) == nudge.settings.monthly_reel_cap and user_row(plain)["own_reel_group"] == "plain", str(user_row(plain)))
        groups = client.get("/health").json()["queue_debug"].get("own_reel_groups") or {}
        check("the health page counts both groups", groups.get("egg", {}).get("people", 0) >= 1 and groups.get("plain", {}).get("people", 0) >= 1, str(groups))

        own_share = plain_ids[1]
        before = len(SENT)
        fired, sent = deliver(client, message(own_share, attachments=[own_reel]))
        check("our own reel shared back is saved", reels_of(own_share) == 1 and "own_saved" in outcomes(own_share), str(outcomes(own_share)))
        check("our own reel shared back is told it is saved", len(SENT) == before + 1 and SENT[-1]["text"].startswith("Saved that reel to your library."), str(SENT[before:]))
        check("the saved line never writes clipnest.in", "clipnest.in" not in SENT[-1]["text"], SENT[-1]["text"])
        own_state = nudge.load_state(user_row(own_share)["id"])
        check("our reel is not counted as one of theirs", own_state["reel_count"] == 0 and own_state["own_reel_saved"], str(own_state["reel_count"]))
        with get_connection() as c:
            own_row = c.execute("SELECT source, status FROM reels WHERE user_id = ?", (user_row(own_share)["id"],)).fetchone()
            queued = c.execute("SELECT COUNT(*) FROM processing_jobs WHERE reel_id = (SELECT id FROM reels WHERE user_id = ?)", (user_row(own_share)["id"],)).fetchone()[0]
        check("it is marked as ours and queued once", own_row["source"] == "clipnest_ad" and queued == 1, str(dict(own_row)))
        check("with their library button", SENT[-1]["labels"] == ["Open my library"] and SENT[-1]["urls"][0].startswith("https://clipnest.in/g/"), str(SENT[-1]))
        with get_connection() as c:
            c.execute("UPDATE nudge_log SET sent_at = '2026-01-01T00:00:00+00:00' WHERE user_id = ?", (user_row(own_share)["id"],))
        before = len(SENT)
        deliver(client, message(own_share, attachments=[{"type": "ig_reel", "payload": {"reel_video_id": "17900000000000001", "url": "https://lookaside.fbsbx.com/x"}}]))
        check("our own reel by id, a second time, gets the short line", len(SENT) == before + 1 and SENT[-1]["text"].startswith("That reel is in your library."), str(SENT[before:]))
        check("a different reel of ours is its own copy", reels_of(own_share) == 2, str(outcomes(own_share)))
        check("also with the library button", SENT[-1]["labels"] == ["Open my library"], str(SENT[-1]))
        with get_connection() as c:
            c.execute("UPDATE users SET last_dm_at = '' WHERE instagram_user_id = ?", (own_share,))
        before = len(SENT)
        nudge.fire(user_row(own_share)["id"], "timer")
        check("the next day reminder reaches someone with no reels, with the library button", len(SENT) == before + 1 and SENT[-1]["text"].startswith("Still here whenever you find a reel") and SENT[-1]["labels"] == ["Open my library"], str(SENT[before:]))
        check("and still the same two", reels_of(own_share) == 2)
        before = len(SENT)
        deliver(client, message("own_link", "https://www.instagram.com/reel/OURPOST01/"))
        check("a pasted link to our own reel is saved, with one reply", reels_of("own_link") == 1 and len(SENT) == before + 1 and SENT[-1]["labels"] == ["Open my library"], str(SENT[before:]))
        before = len(SENT)
        deliver(client, message("own_link", "https://www.instagram.com/reel/OURPOST01/"))
        check("the same link again is not a second copy but still gets the library", reels_of("own_link") == 1 and len(SENT) == before + 1 and SENT[-1]["text"].startswith("That reel is in your library.") and SENT[-1]["labels"] == ["Open my library"], str(SENT[before:]) + str(FIRED[-2:]) + str(outcomes("own_link")))

        from app.services.reel_ingest import sync_reel_items_from_accumulated
        import csv as _csv
        own_uid = user_row("own_link")["id"]
        with get_connection() as c:
            own_url = c.execute("SELECT url FROM reels WHERE user_id = ?", (own_uid,)).fetchone()[0]
        acc = os.path.join(_tmp, "acc.csv")
        with open(acc, "w", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=["URL", "Item Name", "Primary Category"])
            w.writeheader()
            w.writerow({"URL": own_url, "Item Name": "Reel saving app demo", "Primary Category": "Tech"})
        sync_reel_items_from_accumulated(own_uid, acc)
        with get_connection() as c:
            name = c.execute("SELECT item_name FROM reel_items WHERE reel_id = (SELECT id FROM reels WHERE user_id = ?)", (own_uid,)).fetchone()[0]
        check("our reel is named ClipNest ad in the library", name == "ClipNest ad", name)

        no_bare_site = [m["text"] for m in SENT if re.search(r"(?<!@)clipnest\.in", m["text"])]
        check("no bot message writes the website as text", not no_bare_site, str(no_bare_site[:2]))

        before = len(SENT)
        deliver(client, message("real_photo", attachments=[AD_PICTURE]))
        check("a real photo, not from the ad, still gets the share line", len(SENT) == before + 1 and SENT[-1]["text"].startswith("Instagram did not send me the link for that one."), str(SENT[before:]))

        for sender, text, answer in (("q_free", "Is it really free?", FREE_ANSWER), ("q_how", "how does this work", HOW_ANSWER), ("q_share", "I want to share a reel", SHARE_ANSWER)):
            fired, sent = deliver(client, message(sender, text))
            check(f"typed {text!r} gets its fixed answer", len(sent) == 1 and sent[0]["text"].startswith(answer), str(sent))
            fired, sent = deliver(client, message(sender, text))
            check(f"typed {text!r} again gets the short how line", len(sent) == 1 and sent[0]["text"].startswith(AGAIN_TEXT) and "needs_human" in outcomes(sender), str(sent))
        fired, sent = deliver(client, postback("q_tap", "ICE_SHARE", "I want to share a reel"))
        check("a tapped share question gets the share steps", len(sent) == 1 and sent[0]["text"].startswith(SHARE_ANSWER), str(sent))
        fired, sent = deliver(client, message("q_free", "Can you show examples?"))
        check("other words just after the short how line wait for Shlok (its cooldown)", sent == [] and outcomes("q_free")[-1] == "needs_human", str(sent))

        import threading as _threading

        deliver(client, message("racer", "hi"))
        racer = user_row("racer")["id"]
        before = len(SENT)
        threads = [_threading.Thread(target=nudge.fire, args=(racer, "ad_q_free")) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        check("six replies racing for one person send one answer", len(SENT) == before + 1, str(SENT[before:]))

        # --- core users (joined before 14 Oct) stay untouched ---------------
        deliver(client, message("core", "https://www.instagram.com/reel/CORE11111/"))
        with get_connection() as c:
            c.execute("UPDATE users SET created_at = '2026-10-01T10:00:00+00:00' WHERE instagram_user_id = 'core'")
        fired, sent = deliver(client, message("core", "hello"))
        check("a core user typing hello hears nothing and is flagged", sent == [] and "needs_human" in outcomes("core"), str(sent))

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

        # --- a link code from a second account (2026-10-18) ----------------
        from app.services import auth as auth_service

        def full_row(user_id: str) -> dict:
            with get_connection() as c:
                row = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                reels = [tuple(r) for r in c.execute("SELECT * FROM reels WHERE user_id = ? ORDER BY id", (user_id,))]
            # When they last wrote or heard from the bot moves with any
            # message; everything that makes up the account must not.
            account = {k: v for k, v in dict(row).items() if k not in ("last_inbound_at", "last_dm_at")} if row else None
            return {"row": account, "reels": reels}

        # Onir's case: DM account with a reel, then an empty Google account.
        deliver(client, message("joiner", "https://www.instagram.com/reel/JOIN0001/"))
        guest_id = user_row("joiner")["id"]
        newcomer = auth_service.login_or_create_google_user({"sub": "g-joiner", "email": "joiner@example.com", "name": "Joiner"})
        code = auth_service.create_instagram_link_code(newcomer["id"])["code"]
        before = len(SENT)
        deliver(client, message("joiner", code))
        joined = full_row(guest_id)["row"]
        check("a code from the empty second account joins the two", "joined" in outcomes("joiner") and joined["google_sub"] == "g-joiner" and joined["email"] == "joiner@example.com", str(outcomes("joiner")))
        check("the reel stays where it was", len(full_row(guest_id)["reels"]) == 1)
        check("the empty account gives up its Google sign in", not full_row(newcomer["id"])["row"]["google_sub"])
        check("the bot says it is linked, with the library", len(SENT) == before + 1 and SENT[-1]["text"] == "Linked. Your reels are in your library." and SENT[-1]["labels"], str(SENT[before:]))
        check("signing in with that Google again opens the joined account", auth_service.login_or_create_google_user({"sub": "g-joiner", "email": "joiner@example.com"})["id"] == guest_id)

        class _Req:
            def __init__(self, user_id):
                self.session = {auth_service.SESSION_USER_KEY: user_id}

        req = _Req(newcomer["id"])
        check("the browser still signed in to the empty account follows it", (auth_service.current_user(req) or {}).get("id") == guest_id and req.session[auth_service.SESSION_USER_KEY] == guest_id)

        # Early users have Google and Instagram both. Nothing may touch them.
        prime = {}
        for name in ("vedant", "rohan", "saatwik"):
            deliver(client, message(f"prime_{name}", f"https://www.instagram.com/reel/PRIME{name.upper()[:4]}/"))
            prime_id = user_row(f"prime_{name}")["id"]
            with get_connection() as c:
                c.execute("UPDATE users SET google_sub = ?, email = ? WHERE id = ?", (f"g-{name}", f"{name}@example.com", prime_id))
            prime[name] = (prime_id, full_row(prime_id))
        stranger = auth_service.login_or_create_google_user({"sub": "g-stranger", "email": "stranger@example.com", "name": "S"})
        stranger_before = full_row(stranger["id"])
        before = len(SENT)
        deliver(client, message("prime_vedant", auth_service.create_instagram_link_code(stranger["id"])["code"]))
        check("a new account cannot take an early user's Instagram", "link_failed" in outcomes("prime_vedant"))
        check("and is told so, not left in silence", len(SENT) == before + 1 and "already linked" in SENT[-1]["text"], str(SENT[before:]))
        check("the new account is untouched", full_row(stranger["id"]) == stranger_before)
        rohan_id = prime["rohan"][0]
        deliver(client, message("join_target", "https://www.instagram.com/reel/JOINT001/"))
        target_before = full_row(user_row("join_target")["id"])
        deliver(client, message("join_target", auth_service.create_instagram_link_code(rohan_id)["code"]))
        check("an early user's code cannot pull in someone else's DM account", "link_failed" in outcomes("join_target"))
        check("that DM account is untouched", full_row(user_row("join_target")["id"]) == target_before)
        for name, (prime_id, snapshot) in prime.items():
            check(f"{name} is byte for byte unchanged", full_row(prime_id) == snapshot)
            check(f"{name} cannot be a join target", auth_service.join_accounts(prime_id, stranger["id"]) == "" and full_row(prime_id) == snapshot)

        before = len(SENT)
        deliver(client, message("joiner", "REEL-123456"))
        check("an unknown or expired code gets told to get a new one", len(SENT) == before + 1 and "expired" in SENT[-1]["text"], str(SENT[before:]))

        # --- two more questions it answers by itself ------------------------
        for text, trigger in (
            ("How long does it take?", "ad_q_time"), ("how long", "ad_q_time"),
            ("Is it free forever?", "ad_q_forever"), ("Is it really free?", "ad_q_free"),
            ("How does it work?", "ad_q_how"), ("I want to share a reel", "ad_q_share"),
        ):
            check(f"{text!r} is read as {trigger}", nudge.ad_question(text) == trigger, nudge.ad_question(text))
        deliver(client, message("asker", "https://www.instagram.com/reel/ASK00001/"))
        before = len(SENT)
        deliver(client, message("asker", "How long does it take?"))
        deliver(client, message("asker", "Is it free forever?"))
        check("how long gets its answer", any(m["text"].startswith("Usually a minute or two") for m in SENT[before:]), str(SENT[before:]))
        check("free forever gets its answer", any(m["text"] == "Yes, it is free right now. If that ever changes I will tell you first." for m in SENT[before:]), str(SENT[before:]))
        before = len(SENT)
        deliver(client, message("asker", "How long does it take?"))
        check("the same question twice gets the short how line", len(SENT) == before + 1 and SENT[-1]["text"].startswith(AGAIN_TEXT) and "needs_human" in outcomes("asker"), str(SENT[before:]))

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
