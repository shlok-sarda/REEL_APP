from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.schemas import GoogleLoginRequest, InstagramLinkStartResponse, ProfileNameRequest, SessionResponse, TelegramLinkCompleteRequest, UserProfile
from app.services.events import record_landing_event
from app.services.auth import (
    DEMO_LINK_SESSION_KEY,
    GUEST_LINK_SESSION_KEY,
    SESSION_CSRF_KEY,
    SESSION_USER_KEY,
    attach_google_to_user,
    block_link_session_writes,
    build_library_link,
    create_instagram_link_code,
    disconnect_instagram,
    build_telegram_link_url,
    complete_telegram_link,
    create_login_csrf,
    current_user,
    get_user_by_google_sub,
    get_user_by_id,
    is_demo_link_session,
    is_guest_link_session,
    login_or_create_google_user,
    normalize,
    set_preferred_name,
    user_is_admin,
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
            preferred_name=user["preferred_name"],
            email=user["email"],
            picture_url=user["picture_url"],
            telegram_user_id=user["telegram_user_id"],
            telegram_username=user["telegram_username"],
            instagram_user_id=user["instagram_user_id"],
            instagram_username=user["instagram_username"],
            is_admin=user_is_admin(user),
        ),
        telegram_connected=bool(user["telegram_user_id"]),
        instagram_connected=bool(user["instagram_user_id"]),
        guest=is_guest_link_session(request),
        demo=is_demo_link_session(request),
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
    google_sub = normalize(token_payload.get("sub"))
    # Checked before the call, because login_or_create_google_user upserts and
    # cannot tell us afterwards whether this was a new account or a return
    # visit. Only the first one is a signup.
    existing_google = get_user_by_google_sub(google_sub)
    is_new_user = existing_google is None

    # A guest signing in from their own library. Their reels and their
    # Instagram link live on the guest row, so Google is attached to that row
    # rather than a fresh one being created - creating one is what used to
    # land a guest in an empty library at the exact moment they committed.
    guest_id = ""
    if request.session.get(GUEST_LINK_SESSION_KEY):
        guest = get_user_by_id(normalize(request.session.get(SESSION_USER_KEY)))
        if guest and not normalize(guest.get("google_sub")):
            guest_id = guest["id"]

    if guest_id and existing_google and existing_google["id"] != guest_id:
        # Two real libraries for one person. Merging them automatically means
        # moving rows between accounts, which is where data gets lost; at
        # this size it is safer to refuse and fix it by hand.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That Google account already has its own ClipNest library. Message us on Instagram and we will join the two.",
        )

    if guest_id and is_new_user:
        user = attach_google_to_user(guest_id, token_payload)
        if not user:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This library is already linked to a Google account.")
        # Reels sent after the 20-reel wall were held, not processed. Now
        # that they have signed in, the wall is gone, so play them through.
        # "Sign in and it saves straight away" has to be true.
        try:
            from app.api.routes.instagram import _drain_buffered_reels
            from app.services.jobs import ensure_background_progress

            igsid = normalize(user.get("instagram_user_id"))
            if igsid and _drain_buffered_reels(igsid, normalize(user.get("instagram_username")), user["id"]):
                ensure_background_progress()
        except Exception as exc:  # a failed drain must not fail the sign-in
            print(f"[auth] held-reel drain after guest sign-in failed: {exc}")
    else:
        user = login_or_create_google_user(token_payload)
    if is_new_user:
        record_landing_event("signup", visitor=payload.visitor)
    request.session[SESSION_USER_KEY] = user["id"]
    # A real Google sign-in proves who is holding the session, so it lifts the
    # bearer-link restriction. Left in place, a library-link visitor who then
    # signs in stays locked out of delete until they log out and back in.
    request.session.pop(GUEST_LINK_SESSION_KEY, None)
    request.session.pop(DEMO_LINK_SESSION_KEY, None)
    request.session[SESSION_CSRF_KEY] = create_login_csrf(request)
    return _session_payload(request)


@router.post("/profile-name", response_model=SessionResponse)
def profile_name(payload: ProfileNameRequest, request: Request):
    block_link_session_writes(request, "rename the account")
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in first")
    set_preferred_name(user["id"], payload.name)
    return _session_payload(request)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return JSONResponse({"ok": True})


@router.get("/telegram/connect")
def telegram_connect(request: Request):
    block_link_session_writes(request, "link accounts")
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url=build_telegram_link_url(user["id"]), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/instagram/connect", response_model=InstagramLinkStartResponse)
def instagram_connect(request: Request):
    block_link_session_writes(request, "link accounts")
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in first")
    payload = create_instagram_link_code(user["id"])
    return InstagramLinkStartResponse(
        code=payload["code"],
        instagram_username=payload["instagram_username"],
        expires_at=payload["expires_at"],
    )


@router.post("/instagram/disconnect")
def instagram_disconnect(request: Request):
    block_link_session_writes(request, "unlink accounts")
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in first")
    disconnect_instagram(user["id"])
    return JSONResponse({"ok": True})


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


@router.get("/library-link")
def library_link(request: Request):
    """This account's own /g/<token> link.

    Signed-in only, and never available to a session that itself arrived by
    bearer link - otherwise holding someone's link would hand you a permanent
    copy of it through the API.
    """
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in first")
    block_link_session_writes(request, "view your library link")
    return JSONResponse({"ok": True, "url": build_library_link(user["id"])})
