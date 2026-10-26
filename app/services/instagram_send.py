"""Send a DM from the app's Instagram account.

The whole guest flow depends on being able to reply to a DM: the personal
library link, the milestone nudges and the sign-in prompt are all outbound
messages. Nothing in this repo had ever sent one, so this module exists to
prove the channel works before anything is built on top of it.

    POST https://graph.instagram.com/<ver>/me/messages
    Authorization: Bearer <INSTAGRAM_ACCESS_TOKEN>
    {"recipient": {"id": "<IGSID>"}, "message": {"text": "..."}}

Meta only accepts this inside the 24-hour window that opens when the person
messages us, and every message they send resets it. There is no way to reach
someone who has gone quiet: the HUMAN_AGENT tag extends the window to 7 days
but requires App Review and is explicitly not for automation. So every send
here is a reply to something they just did, never a standalone broadcast.

Failure is always returned, never raised. The caller is the ingest webhook and
a failed reply must not cost the user their reel.
"""

from __future__ import annotations

import requests

from app.config import settings
from app.services import dm_outgoing, instagram_token

GRAPH_HOST = "https://graph.instagram.com"
# Meta's send endpoint has repeatedly taken longer than 8s from Render, and
# every timeout is a message the person never receives. Raised - and the call
# is made off the webhook's request path, so a slow send no longer holds up
# the reply Instagram is waiting for.
REQUEST_TIMEOUT_SECONDS = 25
# Meta rejects anything longer. Truncate rather than fail: a clipped nudge
# still works, a 400 means the person hears nothing at all.
MAX_TEXT_BYTES = 1000
# Meta's limits for the richer formats. Anything over is clipped here, for the
# same reason: Instagram cuts a long label silently or rejects the message.
MAX_BUTTON_TEXT_CHARS = 640
MAX_BUTTONS = 3
MAX_BUTTON_TITLE_CHARS = 20
MAX_QUICK_REPLIES = 13
MAX_QUICK_REPLY_TITLE_CHARS = 20
MAX_CARDS = 10
MAX_CARD_TEXT_CHARS = 80
SENDER_ACTIONS = {"mark_seen", "typing_on", "typing_off"}


def sending_enabled() -> bool:
    return bool(settings.instagram_access_token)


def _clip(text: str) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_TEXT_BYTES:
        return text
    return encoded[:MAX_TEXT_BYTES].decode("utf-8", errors="ignore")


def _post(igsid: str, body: dict, timeout: float = REQUEST_TIMEOUT_SECONDS) -> dict:
    """One call to the send endpoint. Returns {"ok": bool, "detail": str}."""
    igsid = (igsid or "").strip()
    if not igsid:
        return {"ok": False, "detail": "no recipient igsid"}
    if not sending_enabled():
        return {"ok": False, "detail": "INSTAGRAM_ACCESS_TOKEN is not set"}

    url = f"{GRAPH_HOST}/{settings.instagram_graph_version}/me/messages"
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {instagram_token.current_token()}"},
            json={"recipient": {"id": igsid}, **body},
            timeout=timeout,
        )
    except Exception as exc:
        return {"ok": False, "detail": f"request_failed: {exc}"}

    instagram_token.note_result(response.status_code, response.text)
    if response.status_code != 200:
        return {"ok": False, "detail": f"http_{response.status_code}: {response.text[:200]}"}
    if "message" in body:
        dm_outgoing.note_bot_send(igsid, body, response.text)
    return {"ok": True, "detail": response.text[:200]}


def send_text(igsid: str, text: str) -> dict:
    """DM one person. Returns {"ok": bool, "detail": str}, never raises."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "detail": "empty message text"}
    return _post(igsid, {"message": {"text": _clip(text)}})


def _clean_buttons(buttons: list) -> list[dict]:
    """Meta's shape for each button, with over-long labels clipped. A button
    that could not work (no label, no target) is dropped rather than sent."""
    cleaned = []
    for button in buttons or []:
        if not isinstance(button, dict):
            continue
        title = str(button.get("title") or "").strip()[:MAX_BUTTON_TITLE_CHARS]
        if not title:
            continue
        if button.get("type") == "postback" and str(button.get("payload") or "").strip():
            cleaned.append({"type": "postback", "title": title, "payload": str(button["payload"]).strip()})
        elif str(button.get("url") or "").startswith("http"):
            cleaned.append({"type": "web_url", "title": title, "url": str(button["url"])})
    return cleaned[:MAX_BUTTONS]


def send_button_template(igsid: str, text: str, buttons: list) -> dict:
    """A short line with one to three labelled buttons under it. Shown in the
    Instagram app only, not on Instagram web."""
    text = (text or "").strip()[:MAX_BUTTON_TEXT_CHARS]
    cleaned = _clean_buttons(buttons)
    if not text:
        return {"ok": False, "detail": "empty message text"}
    if not cleaned:
        return {"ok": False, "detail": "no usable button"}
    return _post(igsid, {"message": {"attachment": {"type": "template", "payload": {
        "template_type": "button", "text": text, "buttons": cleaned,
    }}}})


def send_quick_replies(igsid: str, text: str, replies: list) -> dict:
    """A text message with tappable chips above the keyboard. Tapping one
    sends its title as the person's message, with the payload alongside."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "detail": "empty message text"}
    chips = []
    for reply in replies or []:
        if not isinstance(reply, dict):
            continue
        title = str(reply.get("title") or "").strip()[:MAX_QUICK_REPLY_TITLE_CHARS]
        payload = str(reply.get("payload") or "").strip()
        if title and payload:
            chips.append({"content_type": "text", "title": title, "payload": payload})
    if not chips:
        return {"ok": False, "detail": "no usable quick reply"}
    return _post(igsid, {"message": {"text": _clip(text), "quick_replies": chips[:MAX_QUICK_REPLIES]}})


def send_generic_template(igsid: str, elements: list) -> dict:
    """A row of cards. Nothing sends one yet: the first library message is a
    button template by decision, and reel thumbnails never leave the app."""
    cards = []
    for element in elements or []:
        if not isinstance(element, dict):
            continue
        title = str(element.get("title") or "").strip()[:MAX_CARD_TEXT_CHARS]
        if not title:
            continue
        card: dict = {"title": title}
        subtitle = str(element.get("subtitle") or "").strip()[:MAX_CARD_TEXT_CHARS]
        if subtitle:
            card["subtitle"] = subtitle
        if str(element.get("image_url") or "").startswith("http"):
            card["image_url"] = str(element["image_url"])
        buttons = _clean_buttons(element.get("buttons") or [])
        if buttons:
            card["buttons"] = buttons
        cards.append(card)
    if not cards:
        return {"ok": False, "detail": "no usable card"}
    return _post(igsid, {"message": {"attachment": {"type": "template", "payload": {
        "template_type": "generic", "elements": cards[:MAX_CARDS],
    }}}})


def send_sender_action(igsid: str, action: str, timeout: float = REQUEST_TIMEOUT_SECONDS) -> dict:
    """Show "seen" or the typing dots. Decoration only: callers ignore a
    failure and pass a short timeout so it cannot hold up the real message."""
    if action not in SENDER_ACTIONS:
        return {"ok": False, "detail": f"unknown sender action {action!r}"}
    return _post(igsid, {"sender_action": action}, timeout=timeout)
