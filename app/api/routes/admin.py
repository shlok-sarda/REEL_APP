from fastapi import APIRouter, Query, Request

from app.services.auth import list_users_admin, require_admin
from app.services.instagram_profile import (
    backfill_usernames,
    backfill_webhook_event_usernames,
    profile_lookup_enabled,
    resolve_instagram_username,
    whois,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def admin_users(request: Request):
    require_admin(request)
    return {"users": list_users_admin()}


@router.get("/instagram/backfill")
def admin_instagram_backfill(
    request: Request,
    force: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=1000),
    events: bool = Query(default=True),
):
    """Resolve @usernames for accounts that linked before lookups existed.

    Every linked user stored an IGSID, so this recovers handles no matter how
    long ago they signed up — including users whose webhook log rows were
    trimmed away by the 200-row retention limit.

    `force=1` re-resolves handles that are already filled in (use after
    someone renames). `events=0` skips stamping the retained webhook log.
    """
    require_admin(request)
    if not profile_lookup_enabled():
        return {
            "ok": False,
            "reason": "INSTAGRAM_ACCESS_TOKEN is not set",
            "fix": "Add INSTAGRAM_ACCESS_TOKEN (instagram_business_basic + instagram_business_manage_messages) in Render, then reload this URL.",
        }
    result = {"users": backfill_usernames(force=force, limit=limit)}
    if events:
        result["webhook_events"] = backfill_webhook_event_usernames(limit=limit)
    return result


@router.get("/instagram/lookup/{igsid}")
def admin_instagram_lookup(request: Request, igsid: str, force: bool = Query(default=False)):
    """Resolve one Instagram-scoped id by hand.

    For answering "who is 1173834432473304?" without running a whole backfill.
    """
    require_admin(request)
    if not profile_lookup_enabled():
        return {"ok": False, "reason": "INSTAGRAM_ACCESS_TOKEN is not set"}
    username = resolve_instagram_username(igsid.strip(), force=force)
    return {
        "igsid": igsid.strip(),
        "username": username,
        "resolved": bool(username),
        "profile_url": f"https://www.instagram.com/{username}/" if username else "",
    }


@router.get("/instagram/whois")
def admin_instagram_whois(request: Request, q: str = Query(..., min_length=2)):
    """Everything known about one account, found by email, name, or IGSID.

    Works for users whose webhook rows expired long ago: the IGSID lives on
    the users row and on the link token they redeemed, so identity outlives
    the 200-row event log. If a token is configured the handle is resolved on
    the spot; if not, the redeemed link code is returned, which is plain text
    inside the Instagram thread and can be searched for by hand.
    """
    require_admin(request)
    return whois(q)
