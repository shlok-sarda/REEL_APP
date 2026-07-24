from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request, status
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from app.config import settings
from app.db.database import get_connection


SESSION_USER_KEY = "user_id"
SESSION_CSRF_KEY = "login_csrf"
# Set only by the /demo-login/<token> magic link — marks a shared-demo session
# so destructive endpoints can refuse it while browsing/search stay fully live.
DEMO_LINK_SESSION_KEY = "demo_link_session"
TELEGRAM_LINK_TTL_MINUTES = 15
INSTAGRAM_LINK_TTL_MINUTES = 15


def normalize(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_user_id(google_sub: str) -> str:
    digest = hashlib.sha256(google_sub.encode("utf-8")).hexdigest()[:16]
    return f"user_{digest}"


def row_to_user(row) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "id": normalize(row["id"]),
        "display_name": normalize(row["display_name"]),
        "email": normalize(row["email"]),
        "picture_url": normalize(row["picture_url"]),
        "google_sub": normalize(row["google_sub"]),
        "telegram_user_id": normalize(row["telegram_user_id"]),
        "telegram_username": normalize(row["telegram_username"]),
        "instagram_user_id": normalize(row["instagram_user_id"]),
        "instagram_username": normalize(row["instagram_username"]),
        "preferred_name": normalize(row["preferred_name"]),
        "created_at": normalize(row["created_at"]),
        "last_login_at": normalize(row["last_login_at"]),
        "updated_at": normalize(row["updated_at"]),
    }


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, display_name, email, picture_url, google_sub, telegram_user_id,
                   telegram_username, instagram_user_id, instagram_username, preferred_name, created_at, last_login_at, updated_at
            FROM users
            WHERE id = ?
            LIMIT 1
            """,
            (normalize(user_id),),
        ).fetchone()
    return row_to_user(row)


def get_user_by_email(email: str) -> dict[str, Any] | None:
    normalized = normalize(email).lower()
    if not normalized:
        return None
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, display_name, email, picture_url, google_sub, telegram_user_id,
                   telegram_username, instagram_user_id, instagram_username, preferred_name, created_at, last_login_at, updated_at
            FROM users
            WHERE lower(email) = ?
            LIMIT 1
            """,
            (normalized,),
        ).fetchone()
    return row_to_user(row)


def get_user_by_google_sub(google_sub: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, display_name, email, picture_url, google_sub, telegram_user_id,
                   telegram_username, instagram_user_id, instagram_username, preferred_name, created_at, last_login_at, updated_at
            FROM users
            WHERE google_sub = ?
            LIMIT 1
            """,
            (normalize(google_sub),),
        ).fetchone()
    return row_to_user(row)


def get_user_by_telegram_user_id(telegram_user_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, display_name, email, picture_url, google_sub, telegram_user_id,
                   telegram_username, instagram_user_id, instagram_username, preferred_name, created_at, last_login_at, updated_at
            FROM users
            WHERE telegram_user_id = ?
            LIMIT 1
            """,
            (normalize(telegram_user_id),),
        ).fetchone()
    return row_to_user(row)


def get_user_by_instagram_user_id(instagram_user_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, display_name, email, picture_url, google_sub, telegram_user_id,
                   telegram_username, instagram_user_id, instagram_username, preferred_name, created_at, last_login_at, updated_at
            FROM users
            WHERE instagram_user_id = ?
            LIMIT 1
            """,
            (normalize(instagram_user_id),),
        ).fetchone()
    return row_to_user(row)


def create_login_csrf(request: Request) -> str:
    token = secrets.token_urlsafe(24)
    request.session[SESSION_CSRF_KEY] = token
    return token


def verify_google_credential(credential: str) -> dict[str, Any]:
    if not settings.google_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google login is not configured")
    try:
        payload = id_token.verify_oauth2_token(
            credential,
            GoogleRequest(),
            settings.google_client_id,
        )
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Google login failed: {exc}") from exc

    issuer = normalize(payload.get("iss"))
    if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token issuer")

    return payload


def login_or_create_google_user(payload: dict[str, Any]) -> dict[str, Any]:
    google_sub = normalize(payload.get("sub"))
    email = normalize(payload.get("email"))
    display_name = normalize(payload.get("name")) or (email.split("@")[0] if email else "User")
    picture_url = normalize(payload.get("picture"))
    now = iso_now()
    existing = get_user_by_google_sub(google_sub)

    if existing:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE users
                SET display_name = ?, email = ?, picture_url = ?, last_login_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (display_name, email, picture_url, now, now, existing["id"]),
            )
        return get_user_by_id(existing["id"]) or existing

    user_id = build_user_id(google_sub)
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO users (
                id, telegram_user_id, display_name, created_at, google_sub, email, picture_url,
                telegram_username, instagram_user_id, instagram_username, last_login_at, updated_at
            )
            VALUES (?, NULL, ?, ?, ?, ?, ?, '', '', '', ?, ?)
            """,
            (user_id, display_name, now, google_sub, email, picture_url, now, now),
        )
    return get_user_by_id(user_id)


def current_user(request: Request) -> dict[str, Any] | None:
    user_id = normalize(request.session.get(SESSION_USER_KEY))
    if not user_id:
        return None
    return get_user_by_id(user_id)


def require_user(request: Request) -> dict[str, Any]:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in first")
    return user


def user_is_admin(user: dict[str, Any] | None) -> bool:
    if not user:
        return False
    email = normalize(user.get("email")).lower()
    return bool(email) and email in settings.admin_emails


def require_admin(request: Request) -> dict[str, Any]:
    user = require_user(request)
    if not user_is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user


def is_demo_link_session(request: Request) -> bool:
    return bool(request.session.get(DEMO_LINK_SESSION_KEY))


def block_demo_link_writes(request: Request, action: str) -> None:
    if is_demo_link_session(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This shared demo account can't {action}. Browsing, search, and folders are all open — explore away.",
        )


def set_preferred_name(user_id: str, name: str) -> dict[str, Any] | None:
    cleaned = normalize(name)[:60]
    if not cleaned:
        return get_user_by_id(user_id)
    with get_connection() as connection:
        connection.execute(
            "UPDATE users SET preferred_name = ?, updated_at = ? WHERE id = ?",
            (cleaned, iso_now(), user_id),
        )
    return get_user_by_id(user_id)


def list_users_admin() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT u.id, u.display_name, u.preferred_name, u.email, u.created_at, u.last_login_at,
                   u.instagram_username, u.instagram_user_id,
                   (SELECT COUNT(*) FROM reels r WHERE r.user_id = u.id) AS reel_count
            FROM users u
            ORDER BY (u.last_login_at = '') ASC, u.last_login_at DESC, u.created_at DESC
            """
        ).fetchall()
    return [
        {
            "id": normalize(row["id"]),
            "name": normalize(row["preferred_name"]) or normalize(row["display_name"]),
            "google_name": normalize(row["display_name"]),
            "email": normalize(row["email"]),
            "created_at": normalize(row["created_at"]),
            "last_login_at": normalize(row["last_login_at"]),
            "instagram_username": normalize(row["instagram_username"]),
            "instagram_connected": bool(normalize(row["instagram_user_id"])),
            "reel_count": int(row["reel_count"] or 0),
        }
        for row in rows
    ]


def ensure_user_access(request: Request, requested_user_id: str | None, allow_demo: bool = False) -> str:
    normalized = normalize(requested_user_id)
    if allow_demo and normalized.lower() == "demo":
        return "demo"
    user = require_user(request)
    if normalized and normalized != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access another user's library")
    return user["id"]


def create_telegram_link_code(user_id: str) -> str:
    code = secrets.token_urlsafe(18)
    now = utc_now()
    expires_at = now + timedelta(minutes=TELEGRAM_LINK_TTL_MINUTES)
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM telegram_link_tokens WHERE user_id = ? OR expires_at < ? OR used_at != ''",
            (normalize(user_id), now.isoformat(timespec="seconds")),
        )
        connection.execute(
            """
            INSERT INTO telegram_link_tokens (code, user_id, created_at, expires_at, used_at, telegram_user_id)
            VALUES (?, ?, ?, ?, '', '')
            """,
            (code, normalize(user_id), now.isoformat(timespec="seconds"), expires_at.isoformat(timespec="seconds")),
        )
    return code


def complete_telegram_link(code: str, telegram_user_id: str, telegram_username: str = "", telegram_display_name: str = "") -> dict[str, Any]:
    normalized_code = normalize(code)
    normalized_tg_id = normalize(telegram_user_id)
    with get_connection() as connection:
        token_row = connection.execute(
            """
            SELECT code, user_id, created_at, expires_at, used_at, telegram_user_id
            FROM telegram_link_tokens
            WHERE code = ?
            LIMIT 1
            """,
            (normalized_code,),
        ).fetchone()
        if not token_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This Telegram link has expired or is invalid")
        token = dict(token_row)
        if normalize(token.get("used_at")):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This Telegram link has already been used")
        if parse_iso(token["expires_at"]) < utc_now():
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="This Telegram link has expired")

        existing_owner = connection.execute(
            "SELECT id FROM users WHERE telegram_user_id = ? LIMIT 1",
            (normalized_tg_id,),
        ).fetchone()
        if existing_owner and normalize(existing_owner["id"]) != normalize(token["user_id"]):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This Telegram account is already linked to another user")

        now = iso_now()
        connection.execute(
            """
            UPDATE users
            SET telegram_user_id = ?, telegram_username = ?, updated_at = ?
            WHERE id = ?
            """,
            (normalized_tg_id, normalize(telegram_username), now, normalize(token["user_id"])),
        )
        connection.execute(
            """
            UPDATE telegram_link_tokens
            SET used_at = ?, telegram_user_id = ?
            WHERE code = ?
            """,
            (now, normalized_tg_id, normalized_code),
        )
    return get_user_by_id(token["user_id"]) or {}


def build_telegram_link_url(user_id: str) -> str:
    if not settings.telegram_bot_username:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Telegram bot username is not configured")
    code = create_telegram_link_code(user_id)
    return f"https://t.me/{settings.telegram_bot_username}?start={code}"


def create_instagram_link_code(user_id: str) -> dict[str, str]:
    if not settings.instagram_app_username:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Instagram app username is not configured")
    code = f"REEL-{secrets.randbelow(900000) + 100000}"
    now = utc_now()
    expires_at = now + timedelta(minutes=INSTAGRAM_LINK_TTL_MINUTES)
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM instagram_link_tokens WHERE user_id = ? OR expires_at < ? OR used_at != ''",
            (normalize(user_id), now.isoformat(timespec="seconds")),
        )
        connection.execute(
            """
            INSERT INTO instagram_link_tokens (
                code, user_id, created_at, expires_at, used_at, instagram_user_id, instagram_username
            )
            VALUES (?, ?, ?, ?, '', '', '')
            """,
            (code, normalize(user_id), now.isoformat(timespec="seconds"), expires_at.isoformat(timespec="seconds")),
        )
    return {
        "code": code,
        "instagram_username": settings.instagram_app_username,
        "expires_at": expires_at.isoformat(timespec="seconds"),
    }


def complete_instagram_link(code: str, instagram_user_id: str, instagram_username: str = "") -> dict[str, Any]:
    normalized_code = normalize(code).upper()
    normalized_ig_id = normalize(instagram_user_id)
    normalized_ig_username = normalize(instagram_username).lstrip("@")
    with get_connection() as connection:
        token_row = connection.execute(
            """
            SELECT code, user_id, created_at, expires_at, used_at, instagram_user_id, instagram_username
            FROM instagram_link_tokens
            WHERE code = ?
            LIMIT 1
            """,
            (normalized_code,),
        ).fetchone()
        if not token_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This Instagram link has expired or is invalid")
        token = dict(token_row)
        if normalize(token.get("used_at")):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This Instagram link has already been used")
        if parse_iso(token["expires_at"]) < utc_now():
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="This Instagram link has expired")

        existing_owner = connection.execute(
            "SELECT id FROM users WHERE instagram_user_id = ? LIMIT 1",
            (normalized_ig_id,),
        ).fetchone()
        if existing_owner and normalize(existing_owner["id"]) != normalize(token["user_id"]):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This Instagram account is already linked to another user")

        now = iso_now()
        connection.execute(
            """
            UPDATE users
            SET instagram_user_id = ?, instagram_username = ?, updated_at = ?
            WHERE id = ?
            """,
            (normalized_ig_id, normalized_ig_username, now, normalize(token["user_id"])),
        )
        connection.execute(
            """
            UPDATE instagram_link_tokens
            SET used_at = ?, instagram_user_id = ?, instagram_username = ?
            WHERE code = ?
            """,
            (now, normalized_ig_id, normalized_ig_username, normalized_code),
        )
    return get_user_by_id(token["user_id"]) or {}


def disconnect_instagram(user_id: str) -> dict[str, Any]:
    """Release the Instagram account linked to this user so it can be linked elsewhere.

    Clears only the link fields on the users row — the user's reels, collections and
    all other data remain keyed to their user_id and are left untouched.
    """
    normalized_user = normalize(user_id)
    now = iso_now()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET instagram_user_id = '', instagram_username = '', updated_at = ?
            WHERE id = ?
            """,
            (now, normalized_user),
        )
        # Drop any pending link codes for this user so stale codes can't re-link.
        connection.execute(
            "DELETE FROM instagram_link_tokens WHERE user_id = ?",
            (normalized_user,),
        )
    return get_user_by_id(normalized_user) or {}
