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

GRAPH_HOST = "https://graph.instagram.com"
# Meta's send endpoint has repeatedly taken longer than 8s from Render, and
# every timeout is a message the person never receives. Raised - and the call
# is made off the webhook's request path, so a slow send no longer holds up
# the reply Instagram is waiting for.
REQUEST_TIMEOUT_SECONDS = 25
# Meta rejects anything longer. Truncate rather than fail: a clipped nudge
# still works, a 400 means the person hears nothing at all.
MAX_TEXT_BYTES = 1000


def sending_enabled() -> bool:
    return bool(settings.instagram_access_token)


def _clip(text: str) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_TEXT_BYTES:
        return text
    return encoded[:MAX_TEXT_BYTES].decode("utf-8", errors="ignore")


def send_text(igsid: str, text: str) -> dict:
    """DM one person. Returns {"ok": bool, "detail": str}, never raises."""
    igsid = (igsid or "").strip()
    text = (text or "").strip()
    if not igsid:
        return {"ok": False, "detail": "no recipient igsid"}
    if not text:
        return {"ok": False, "detail": "empty message text"}
    if not sending_enabled():
        return {"ok": False, "detail": "INSTAGRAM_ACCESS_TOKEN is not set"}

    url = f"{GRAPH_HOST}/{settings.instagram_graph_version}/me/messages"
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {settings.instagram_access_token}"},
            json={"recipient": {"id": igsid}, "message": {"text": _clip(text)}},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        return {"ok": False, "detail": f"request_failed: {exc}"}

    if response.status_code != 200:
        return {"ok": False, "detail": f"http_{response.status_code}: {response.text[:200]}"}
    return {"ok": True, "detail": response.text[:200]}
