"""Is this reel one of ours?

People who see the @clipnest.in ad or a ClipNest reel often share that same
reel back into the chat. It is not something they want to keep: saving it
put our own ad in their library and told them "Got it, watching that reel".

    GET https://graph.instagram.com/<ver>/me/media?fields=id,shortcode

lists the account's own posts and reels. The ids and shortcodes are cached,
because a share back is checked on the webhook path and Meta can be slow.
Nothing here raises: when the list cannot be read the answer is "not ours",
which is how every share was treated before this existed.
"""

from __future__ import annotations

import re
import threading
import time

import requests

from app.config import settings
from app.services import instagram_token

GRAPH_HOST = "https://graph.instagram.com"
REQUEST_TIMEOUT_SECONDS = 6
REFRESH_AFTER_SECONDS = 30 * 60
# After a failed read, wait this long before asking Meta again.
RETRY_AFTER_SECONDS = 5 * 60
MAX_PAGES = 5

_SHORTCODE_RE = re.compile(r"instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)", re.IGNORECASE)

_lock = threading.Lock()
_cache: dict = {"ids": set(), "shortcodes": set(), "read_at": 0.0, "tried_at": 0.0}


def _fetch() -> tuple[set[str], set[str]] | None:
    token = instagram_token.current_token()
    if not token:
        return None
    url = f"{GRAPH_HOST}/{settings.instagram_graph_version}/me/media"
    params = {"fields": "id,shortcode", "limit": 100}
    ids: set[str] = set()
    shortcodes: set[str] = set()
    for _ in range(MAX_PAGES):
        try:
            response = requests.get(
                url, params=params, headers={"Authorization": f"Bearer {token}"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                return None
            body = response.json()
        except Exception:
            return None
        for item in body.get("data") or []:
            if isinstance(item, dict):
                if item.get("id"):
                    ids.add(str(item["id"]))
                if item.get("shortcode"):
                    shortcodes.add(str(item["shortcode"]))
        next_url = (body.get("paging") or {}).get("next")
        if not next_url:
            break
        url, params = next_url, None
    return ids, shortcodes


def _known() -> tuple[set[str], set[str]]:
    now = time.monotonic()
    with _lock:
        fresh = _cache["read_at"] and now - _cache["read_at"] < REFRESH_AFTER_SECONDS
        recently_failed = _cache["tried_at"] and now - _cache["tried_at"] < RETRY_AFTER_SECONDS
        if fresh or recently_failed:
            return _cache["ids"], _cache["shortcodes"]
        _cache["tried_at"] = now
    fetched = _fetch()
    with _lock:
        if fetched is not None:
            _cache["ids"], _cache["shortcodes"] = fetched
            _cache["read_at"] = time.monotonic()
        return _cache["ids"], _cache["shortcodes"]


def shortcode(url: str) -> str:
    match = _SHORTCODE_RE.search(url or "")
    return match.group(1) if match else ""


def is_own_url(url: str) -> bool:
    code = shortcode(url)
    return bool(code) and code in _known()[1]


def is_own_media_id(media_id: str) -> bool:
    media_id = str(media_id or "").strip()
    return bool(media_id) and media_id in _known()[0]
