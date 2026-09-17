"""Turn an Instagram-scoped sender id (IGSID) into a real @username.

Instagram's messaging webhook never sends a username. It sends only
`sender.id`, an IGSID that is scoped to this app and is not searchable
anywhere inside Instagram itself. That is why every row in
`instagram_webhook_events` had an empty `sender_username`, and why
`users.instagram_username` was blank for every linked account: the value was
read from a field Instagram does not populate.

The only way to get a handle is to ask for it:

    GET https://graph.instagram.com/<ver>/<IGSID>?fields=username,name
        &access_token=<INSTAGRAM_ACCESS_TOKEN>

The token must belong to the app account that received the DM and carry
`instagram_business_basic` + `instagram_business_manage_messages`. Consent
exists only because the person messaged us first, so this cannot be used to
look up strangers — and it returns nothing if they have blocked the account.

Results are cached in `instagram_profile_cache` because an IGSID's handle
changes rarely, every webhook delivery would otherwise cost an API call, and
a failure should not be retried on every single message.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

from app.config import settings
from app.db.database import get_connection

GRAPH_HOST = "https://graph.instagram.com"
REQUEST_TIMEOUT_SECONDS = 8
# A resolved handle is re-checked occasionally (people do rename), while a
# failure is retried sooner so a token fixed at 2am starts working by morning
# without a deploy.
HIT_TTL_DAYS = 30
MISS_TTL_HOURS = 6


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _parse(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat((value or "").strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def profile_lookup_enabled() -> bool:
    """Whether a lookup can even be attempted. Checked before every call so a
    missing token is a silent no-op rather than a stream of failed requests."""
    return bool(settings.instagram_access_token)


def _read_cache(igsid: str) -> dict | None:
    try:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT igsid, username, name, looked_up_at, outcome FROM instagram_profile_cache WHERE igsid = ?",
                (igsid,),
            ).fetchone()
    except Exception:
        return None
    return dict(row) if row else None


def _write_cache(igsid: str, username: str, name: str, outcome: str) -> None:
    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO instagram_profile_cache (igsid, username, name, looked_up_at, outcome)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(igsid) DO UPDATE SET
                    username = excluded.username,
                    name = excluded.name,
                    looked_up_at = excluded.looked_up_at,
                    outcome = excluded.outcome
                """,
                (igsid, username, name, _iso(_now()), outcome[:200]),
            )
    except Exception:
        # Losing a cache write costs one extra API call later. It must never
        # cost an ingested reel.
        pass


def _cache_is_fresh(cached: dict) -> bool:
    looked_up = _parse(cached.get("looked_up_at", ""))
    if not looked_up:
        return False
    age = _now() - looked_up
    if cached.get("username"):
        return age < timedelta(days=HIT_TTL_DAYS)
    return age < timedelta(hours=MISS_TTL_HOURS)


def fetch_instagram_profile(igsid: str) -> dict:
    """One uncached Graph call. Returns {} on any failure, never raises."""
    if not igsid or not profile_lookup_enabled():
        return {}
    url = f"{GRAPH_HOST}/{settings.instagram_graph_version}/{igsid}"
    try:
        response = requests.get(
            url,
            params={"fields": "username,name", "access_token": settings.instagram_access_token},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        _write_cache(igsid, "", "", f"request_failed: {exc}")
        return {}
    if response.status_code != 200:
        _write_cache(igsid, "", "", f"http_{response.status_code}: {response.text[:150]}")
        return {}
    try:
        payload = response.json()
    except ValueError:
        _write_cache(igsid, "", "", "bad_json")
        return {}
    username = str(payload.get("username") or "").strip().lstrip("@")
    name = str(payload.get("name") or "").strip()
    _write_cache(igsid, username, name, "ok" if username else "no_username_in_response")
    return {"username": username, "name": name}


def resolve_instagram_username(igsid: str, force: bool = False) -> str:
    """Cached IGSID -> @username. Returns "" when unknown or unavailable.

    Callers treat an empty string as "no handle yet", never as an error: the
    webhook must keep saving reels whether or not the name lookup works.
    """
    igsid = (igsid or "").strip()
    if not igsid:
        return ""
    if not force:
        cached = _read_cache(igsid)
        if cached and _cache_is_fresh(cached):
            return cached.get("username", "")
    return fetch_instagram_profile(igsid).get("username", "")


def backfill_usernames(force: bool = False, limit: int = 200) -> dict:
    """Fill in `users.instagram_username` for accounts linked before this
    existed. The IGSID was always stored, so every past user is recoverable —
    including ones whose webhook log rows were long since trimmed away.
    """
    if not profile_lookup_enabled():
        return {"ok": False, "reason": "INSTAGRAM_ACCESS_TOKEN is not set", "updated": 0}

    clause = "" if force else "AND (instagram_username IS NULL OR instagram_username = '')"
    try:
        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT id, email, instagram_user_id
                FROM users
                WHERE instagram_user_id IS NOT NULL AND instagram_user_id != '' {clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
    except Exception as exc:
        return {"ok": False, "reason": f"query failed: {exc}", "updated": 0}

    updated = 0
    results: list[dict] = []
    for row in rows:
        igsid = (row["instagram_user_id"] or "").strip()
        username = resolve_instagram_username(igsid, force=force)
        results.append(
            {
                "user_id": row["id"],
                "email": row["email"],
                "igsid": igsid,
                "username": username,
                "resolved": bool(username),
            }
        )
        if not username:
            continue
        try:
            with get_connection() as connection:
                connection.execute(
                    "UPDATE users SET instagram_username = ?, updated_at = ? WHERE id = ?",
                    (username, _iso(_now()), row["id"]),
                )
            updated += 1
        except Exception:
            continue

    return {
        "ok": True,
        "checked": len(results),
        "updated": updated,
        "unresolved": [r for r in results if not r["resolved"]],
        "results": results,
    }


def backfill_webhook_event_usernames(limit: int = 200) -> dict:
    """Stamp handles onto the retained webhook log rows.

    Only fixes what is still in the table — it keeps the most recent 200 rows,
    so anything older is gone for good and can only be recovered through the
    `users` row instead.
    """
    if not profile_lookup_enabled():
        return {"ok": False, "reason": "INSTAGRAM_ACCESS_TOKEN is not set", "updated": 0}
    try:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT sender_id FROM instagram_webhook_events
                WHERE sender_id != '' AND (sender_username IS NULL OR sender_username = '')
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
    except Exception as exc:
        return {"ok": False, "reason": f"query failed: {exc}", "updated": 0}

    updated = 0
    mapping: dict[str, str] = {}
    for row in rows:
        igsid = (row["sender_id"] or "").strip()
        username = resolve_instagram_username(igsid)
        mapping[igsid] = username
        if not username:
            continue
        try:
            with get_connection() as connection:
                cursor = connection.execute(
                    "UPDATE instagram_webhook_events SET sender_username = ? WHERE sender_id = ? AND (sender_username IS NULL OR sender_username = '')",
                    (username, igsid),
                )
                updated += cursor.rowcount or 0
        except Exception:
            continue
    return {"ok": True, "senders": mapping, "rows_updated": updated}


def whois(query: str) -> dict:
    """Everything the database knows about one linked account.

    Answers "who actually DM'd me?" for a user whose webhook rows aged out of
    the 200-row log long ago. The IGSID is stored permanently on the users row
    and in the link token they redeemed, so identity survives even when the
    event log does not — which is the whole reason this function exists rather
    than another query against instagram_webhook_events.
    """
    needle = (query or "").strip().lower()
    if not needle:
        return {"ok": False, "reason": "empty query"}

    like = f"%{needle}%"
    try:
        with get_connection() as connection:
            user = connection.execute(
                """
                SELECT id, display_name, preferred_name, email, created_at, last_login_at,
                       instagram_user_id, instagram_username
                  FROM users
                 WHERE LOWER(email) = ?
                    OR LOWER(email) LIKE ?
                    OR LOWER(display_name) LIKE ?
                    OR LOWER(preferred_name) LIKE ?
                    OR instagram_user_id = ?
                 ORDER BY (LOWER(email) = ?) DESC, created_at DESC
                 LIMIT 1
                """,
                (needle, like, like, like, needle, needle),
            ).fetchone()
            if not user:
                return {"ok": False, "reason": f"no user matched {query!r}"}
            user = dict(user)

            tokens = [
                dict(r)
                for r in connection.execute(
                    """
                    SELECT code, created_at, expires_at, used_at, instagram_user_id
                      FROM instagram_link_tokens
                     WHERE user_id = ?
                     ORDER BY created_at DESC
                    """,
                    (user["id"],),
                ).fetchall()
            ]
            reels = [
                dict(r)
                for r in connection.execute(
                    """
                    SELECT id, url, shortcode, received_at, status, source
                      FROM reels
                     WHERE user_id = ?
                     ORDER BY received_at ASC
                    """,
                    (user["id"],),
                ).fetchall()
            ]
            events = [
                dict(r)
                for r in connection.execute(
                    """
                    SELECT received_at, kind, outcome, detail
                      FROM instagram_webhook_events
                     WHERE sender_id = ?
                     ORDER BY received_at DESC
                     LIMIT 25
                    """,
                    (user["instagram_user_id"] or "\x00",),
                ).fetchall()
            ]
    except Exception as exc:
        return {"ok": False, "reason": f"query failed: {exc}"}

    igsid = (user["instagram_user_id"] or "").strip()
    username = (user["instagram_username"] or "").strip()
    lookup_note = ""
    if igsid and not username:
        if profile_lookup_enabled():
            username = resolve_instagram_username(igsid)
            if not username:
                cached = _read_cache(igsid) or {}
                lookup_note = cached.get("outcome", "") or "lookup returned no username"
        else:
            lookup_note = "INSTAGRAM_ACCESS_TOKEN is not set, so the handle cannot be resolved yet"

    # The code they DM'd is searchable text inside the Instagram thread, which
    # is a way to find the conversation without any API access at all.
    used_codes = [t["code"] for t in tokens if (t.get("used_at") or "").strip()]

    return {
        "ok": True,
        "user": {
            "id": user["id"],
            "name": user["preferred_name"] or user["display_name"],
            "email": user["email"],
            "signed_up": user["created_at"],
            "last_google_login": user["last_login_at"],
        },
        "instagram": {
            "igsid": igsid,
            "username": username,
            "profile_url": f"https://www.instagram.com/{username}/" if username else "",
            "lookup_note": lookup_note,
        },
        "link_codes_redeemed": used_codes,
        "search_your_dms_for": used_codes[0] if used_codes else "",
        "reel_count": len(reels),
        "reels": reels,
        "retained_webhook_rows": events,
    }
