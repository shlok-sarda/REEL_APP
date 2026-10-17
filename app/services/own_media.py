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

# Our own reels, by link, on top of what Meta lists. An ad can be built on a
# reel the account list does not show, so each of our reels and ads goes here
# (or in OWN_REEL_URLS, comma separated). The first one is the ad's reel: it
# is what someone who opens the chat from the ad gets saved when Instagram
# sends nothing that says which reel it was.
OWN_REEL_URLS: list[str] = []

# What one of our reels is called in the person's library.
OWN_REEL_NAME = "ClipNest ad"
# reels.source of one of our reels saved into someone's library. Those are
# left out of every count of their reels: the lock, the month and the bot's.
OWN_SOURCE = "clipnest_ad"

_lock = threading.Lock()
_cache: dict = {"ids": set(), "shortcodes": set(), "by_id": {}, "read_at": 0.0, "tried_at": 0.0}
# Media ids looked up one by one (an ad's post id the list did not show).
_looked_up: dict[str, str] = {}


def _fetch() -> tuple[set[str], set[str], dict[str, str]] | None:
    token = instagram_token.current_token()
    if not token:
        return None
    url = f"{GRAPH_HOST}/{settings.instagram_graph_version}/me/media"
    params = {"fields": "id,shortcode", "limit": 100}
    ids: set[str] = set()
    shortcodes: set[str] = set()
    by_id: dict[str, str] = {}
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
                    if item.get("id"):
                        by_id[str(item["id"])] = str(item["shortcode"])
        next_url = (body.get("paging") or {}).get("next")
        if not next_url:
            break
        url, params = next_url, None
    return ids, shortcodes, by_id


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
            _cache["ids"], _cache["shortcodes"], _cache["by_id"] = fetched
            _cache["read_at"] = time.monotonic()
        return _cache["ids"], _cache["shortcodes"]


def shortcode(url: str) -> str:
    match = _SHORTCODE_RE.search(url or "")
    return match.group(1) if match else ""


def reel_url(code: str) -> str:
    return f"https://www.instagram.com/reel/{code}/" if code else ""


def configured_urls() -> list[str]:
    """OWN_REEL_URLS from the environment, then the list above, in order."""
    from_env = [u.strip() for u in (settings.own_reel_urls or "").split(",") if u.strip()]
    return from_env + [u for u in OWN_REEL_URLS if u not in from_env]


def _configured_shortcodes() -> set[str]:
    return {code for code in (shortcode(u) for u in configured_urls()) if code}


def ad_reel_url() -> str:
    """The reel the ad is built on, or "" when none is set."""
    for url in configured_urls():
        code = shortcode(url)
        if code:
            return reel_url(code)
    return ""


def is_own_url(url: str) -> bool:
    code = shortcode(url)
    return bool(code) and (code in _configured_shortcodes() or code in _known()[1])


def is_own_media_id(media_id: str) -> bool:
    media_id = str(media_id or "").strip()
    return bool(media_id) and media_id in _known()[0]


def _look_up(media_id: str) -> str:
    """The shortcode of one media id, asked of Meta directly. Only our own
    media can be read with our token, so an answer also means it is ours."""
    with _lock:
        if media_id in _looked_up:
            return _looked_up[media_id]
    code = ""
    token = instagram_token.current_token()
    if token:
        try:
            response = requests.get(
                f"{GRAPH_HOST}/{settings.instagram_graph_version}/{media_id}",
                params={"fields": "shortcode"}, headers={"Authorization": f"Bearer {token}"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                code = str((response.json() or {}).get("shortcode") or "")
        except Exception:
            # Not remembered: a slow moment at Meta is not an answer.
            return ""
    with _lock:
        _looked_up[media_id] = code
    return code


def url_for_media_id(media_id: str, ask: bool = False) -> str:
    """The link of one of our reels from its media id, or "". With `ask`, an
    id the account list does not show is looked up on its own (an ad's post
    id, which is ours by definition)."""
    media_id = str(media_id or "").strip()
    if not media_id or not media_id.isdigit():
        return ""
    _known()
    with _lock:
        code = _cache["by_id"].get(media_id, "")
    if not code and ask:
        code = _look_up(media_id)
    return reel_url(code)
