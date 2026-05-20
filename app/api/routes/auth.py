from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.schemas import GoogleLoginRequest, InstagramLinkStartResponse, SessionResponse, TelegramLinkCompleteRequest, UserProfile
from app.services.auth import (
    SESSION_CSRF_KEY,
    SESSION_USER_KEY,
    create_instagram_link_code,
    build_telegram_link_url,
    complete_telegram_link,
    create_login_csrf,
    current_user,
    login_or_create_google_user,
    verify_google_credential,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _session_payload(request: Request) -> SessionResponse:
    user = current_user(request)
    if not user:
        return SessionResponse(authenticated=False, user=None, telegram_connected=False)
    return SessionResponse(
        authenticated=True,
        user=UserProfile(
            id=user["id"],
            display_name=user["display_name"],
            email=user["email"],
            picture_url=user["picture_url"],
            telegram_user_id=user["telegram_user_id"],
            telegram_username=user["telegram_username"],
            instagram_user_id=user["instagram_user_id"],
            instagram_username=user["instagram_username"],
        ),
        telegram_connected=bool(user["telegram_user_id"]),
        instagram_connected=bool(user["instagram_user_id"]),
    )


@router.get("/session", response_model=SessionResponse)
def auth_session(request: Request):
    if SESSION_CSRF_KEY not in request.session:
        create_login_csrf(request)
    return _session_payload(request)


@router.post("/google", response_model=SessionResponse)
def google_login(payload: GoogleLoginRequest, request: Request):
    csrf_token = request.session.get(SESSION_CSRF_KEY, "")
    if not csrf_token or payload.csrf_token != csrf_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid login session. Please refresh and try again.")

    token_payload = verify_google_credential(payload.credential)
    user = login_or_create_google_user(token_payload)
    request.session[SESSION_USER_KEY] = user["id"]
    request.session[SESSION_CSRF_KEY] = create_login_csrf(request)
    return _session_payload(request)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return JSONResponse({"ok": True})


@router.get("/telegram/connect")
def telegram_connect(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url=build_telegram_link_url(user["id"]), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/instagram/connect", response_model=InstagramLinkStartResponse)
def instagram_connect(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in first")
    payload = create_instagram_link_code(user["id"])
    return InstagramLinkStartResponse(
        code=payload["code"],
        instagram_username=payload["instagram_username"],
        expires_at=payload["expires_at"],
    )


@router.post("/telegram-link/complete")
def telegram_link_complete(payload: TelegramLinkCompleteRequest):
    user = complete_telegram_link(
        payload.code,
        payload.telegram_user_id,
        telegram_username=payload.telegram_username,
        telegram_display_name=payload.telegram_display_name,
    )
    return {
        "ok": True,
        "user_id": user.get("id", ""),
        "display_name": user.get("display_name", ""),
        "telegram_user_id": user.get("telegram_user_id", ""),
    }
