"""Keep the Instagram access token alive, and say so loudly when it is not.

The token lasts about 60 days. When it expires, outbound DMs and username
lookups both stop and nothing visible breaks: the reel still saves, the
person simply never hears back. That already happened once for 12 days.

Meta lets a long-lived token be refreshed any time after its first 24 hours,
as long as it has not expired yet:

    GET https://graph.instagram.com/refresh_access_token
        ?grant_type=ig_refresh_token&access_token=<token>
    -> {"access_token": "...", "token_type": "bearer", "expires_in": 5183944}

The refreshed token may be a different string from the one in the env var, so
it is kept in the database and preferred over the env value. The env value
stays the source of truth for *which* token line we are on: paste a new token
into Render and the stored one is dropped, because its source no longer
matches.

Nothing here raises. The callers are the janitor loop and the send path.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import requests

from app.config import settings
from app.db.database import get_connection

GRAPH_HOST = "https://graph.instagram.com"
REQUEST_TIMEOUT_SECONDS = 25
# Weekly keeps the expiry 53 to 60 days out at all times, so even a month of
# failed refreshes leaves weeks to notice.
REFRESH_EVERY_DAYS = 7
# After a failed attempt (too young, network, Meta down) wait before retrying;
# the janitor calls in every couple of minutes.
RETRY_AFTER_HOURS = 6
# Below this the token is in trouble: refreshes have been failing for weeks.
ALARM_DAYS_LEFT = 14

_COLUMNS = (
    "source_hash, token, refreshed_at, expires_at, refresh_attempted_at, "
    "refresh_error, auth_failed_at, auth_error, last_ok_at"
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _parse(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _env_hash() -> str:
    return hashlib.sha256(settings.instagram_access_token.encode("utf-8")).hexdigest()


def _read_state() -> dict:
    try:
        with get_connection() as connection:
            row = connection.execute(
                f"SELECT {_COLUMNS} FROM instagram_token_state WHERE id = 1"
            ).fetchone()
    except Exception:
        return {}
    return dict(row) if row else {}


def _write_state(**fields) -> None:
    """Upsert the single state row. A changed env token resets everything."""
    source = _env_hash()
    try:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT source_hash FROM instagram_token_state WHERE id = 1"
            ).fetchone()
            if not row or row["source_hash"] != source:
                connection.execute("DELETE FROM instagram_token_state")
                connection.execute(
                    "INSERT INTO instagram_token_state (id, source_hash) VALUES (1, ?)",
                    (source,),
                )
            assignments = ", ".join(f"{name} = ?" for name in fields)
            connection.execute(
                f"UPDATE instagram_token_state SET {assignments} WHERE id = 1",
                list(fields.values()),
            )
    except Exception as exc:
        print(f"[instagram_token] state write failed: {exc}", flush=True)


def current_token() -> str:
    """The token to call Meta with: the refreshed one if it descends from the
    env token, otherwise the env token itself."""
    env_token = settings.instagram_access_token
    if not env_token:
        return ""
    state = _read_state()
    if state.get("token") and state.get("source_hash") == _env_hash():
        return state["token"]
    return env_token


def is_auth_failure(status_code: int, body: str) -> bool:
    # 190 is Meta's "access token expired or invalid" OAuthException.
    text = body or ""
    return status_code == 401 or '"code":190' in text.replace(" ", "")


def note_result(status_code: int, body: str) -> None:
    """Record the outcome of a real Graph call, so a dead token shows up in
    /health the first time it costs someone a message."""
    if not settings.instagram_access_token:
        return
    if status_code == 200:
        state = _read_state()
        # One write per day is enough to prove the token works.
        last_ok = _parse(state.get("last_ok_at") or "")
        if state.get("auth_failed_at") or not last_ok or _now() - last_ok > timedelta(days=1):
            _write_state(last_ok_at=_iso(_now()), auth_failed_at="", auth_error="")
    elif is_auth_failure(status_code, body):
        print(f"[instagram_token] AUTH FAILED: {(body or '')[:200]}", flush=True)
        _write_state(auth_failed_at=_iso(_now()), auth_error=(body or "")[:200])


def refresh_now() -> dict:
    """Ask Meta for a fresh 60 days. Returns {"ok": bool, "detail": str}."""
    token = current_token()
    if not token:
        return {"ok": False, "detail": "INSTAGRAM_ACCESS_TOKEN is not set"}
    attempted = _iso(_now())
    try:
        response = requests.get(
            f"{GRAPH_HOST}/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": token},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        # Exception text from requests can carry the full URL, token included.
        detail = f"request_failed: {type(exc).__name__}"
        _write_state(refresh_attempted_at=attempted, refresh_error=detail)
        return {"ok": False, "detail": detail}

    if response.status_code != 200:
        detail = f"http_{response.status_code}: {response.text[:200]}"
        _write_state(refresh_attempted_at=attempted, refresh_error=detail)
        if is_auth_failure(response.status_code, response.text):
            note_result(response.status_code, response.text)
        print(f"[instagram_token] refresh failed: {detail}", flush=True)
        return {"ok": False, "detail": detail}

    try:
        payload = response.json()
        new_token = str(payload["access_token"]).strip()
        expires_in = int(payload.get("expires_in") or 0)
    except (ValueError, KeyError, TypeError):
        _write_state(refresh_attempted_at=attempted, refresh_error="bad_json")
        return {"ok": False, "detail": "bad_json"}
    if not new_token:
        _write_state(refresh_attempted_at=attempted, refresh_error="empty_token")
        return {"ok": False, "detail": "empty_token"}

    expires_at = _iso(_now() + timedelta(seconds=expires_in)) if expires_in else ""
    _write_state(
        token=new_token,
        refreshed_at=attempted,
        expires_at=expires_at,
        refresh_attempted_at=attempted,
        refresh_error="",
    )
    print(f"[instagram_token] refreshed, expires {expires_at or 'unknown'}", flush=True)
    return {"ok": True, "detail": f"expires_at={expires_at}"}


def maybe_refresh() -> None:
    """Janitor entry point. One row read on almost every call."""
    if not settings.instagram_access_token:
        return
    state = _read_state()
    same_line = state.get("source_hash") == _env_hash()
    now = _now()
    if same_line:
        refreshed = _parse(state.get("refreshed_at") or "")
        if refreshed and now - refreshed < timedelta(days=REFRESH_EVERY_DAYS):
            return
        attempted = _parse(state.get("refresh_attempted_at") or "")
        if attempted and now - attempted < timedelta(hours=RETRY_AFTER_HOURS):
            return
    refresh_now()


def status() -> dict:
    """Health view. Never includes the token."""
    if not settings.instagram_access_token:
        return {"ok": False, "reason": "INSTAGRAM_ACCESS_TOKEN is not set"}
    state = _read_state()
    if state.get("source_hash") != _env_hash():
        state = {}
    out: dict = {
        "using": "refreshed" if state.get("token") else "env",
        "refreshed_at": state.get("refreshed_at") or "",
        "expires_at": state.get("expires_at") or "",
        "refresh_error": state.get("refresh_error") or "",
        "auth_failed_at": state.get("auth_failed_at") or "",
        "auth_error": state.get("auth_error") or "",
        "last_ok_at": state.get("last_ok_at") or "",
    }
    expires = _parse(out["expires_at"])
    if expires:
        out["days_left"] = (expires - _now()).days
    reasons = []
    if out["auth_failed_at"]:
        reasons.append("Meta rejected the token: generate a new one and paste it into Render")
    if expires and out["days_left"] < ALARM_DAYS_LEFT:
        reasons.append(f"token expires in {out['days_left']} days and refresh is failing")
    if not expires:
        reasons.append("expiry unknown: no refresh has succeeded yet")
    out["ok"] = not out["auth_failed_at"] and not (expires and out["days_left"] < ALARM_DAYS_LEFT)
    out["reason"] = "; ".join(reasons)
    return out
