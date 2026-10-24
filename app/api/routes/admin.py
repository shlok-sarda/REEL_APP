from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from app.services.auth import current_user, list_users_admin, require_admin, user_is_admin
from app.services.search_log import llm_usage_summary
from app.services.instagram_profile import (
    backfill_usernames,
    backfill_webhook_event_usernames,
    profile_lookup_enabled,
    resolve_instagram_username,
    whois,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_or_not_found(request: Request) -> None:
    """The dashboard does not exist for anyone but the admin: a logged-out
    visitor and a signed-in non-admin both get a plain 404, never a hint
    that there is something to sign in to."""
    if not user_is_admin(current_user(request)):
        raise HTTPException(status_code=404, detail="Not found")


def _dashboard_page(request: Request, page: str) -> HTMLResponse:
    from app.services.admin_stats import dashboard_data
    from app.ui_ux.admin_dashboard import render

    _admin_or_not_found(request)
    return HTMLResponse(render(page, dashboard_data()), headers={"Cache-Control": "no-store, must-revalidate"})


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def admin_dashboard_today(request: Request):
    return _dashboard_page(request, "today")


@router.get("/dashboard/people", response_class=HTMLResponse, include_in_schema=False)
def admin_dashboard_people(request: Request):
    return _dashboard_page(request, "people")


@router.get("/dashboard/bot", response_class=HTMLResponse, include_in_schema=False)
def admin_dashboard_bot(request: Request):
    return _dashboard_page(request, "bot")


@router.get("/dashboard/savers", response_class=HTMLResponse, include_in_schema=False)
def admin_dashboard_savers(request: Request):
    """Instagram people who save the most reels, with a cross-off box. It only
    lists people; blocking happens by hand in Instagram."""
    from app.db.database import get_connection
    from app.services.heavy_savers import heavy_savers
    from app.ui_ux.admin_dashboard import render_savers

    _admin_or_not_found(request)
    with get_connection() as connection:
        data = heavy_savers(connection)
    return HTMLResponse(render_savers(data), headers={"Cache-Control": "no-store, must-revalidate"})


@router.post("/dashboard/savers/cross", include_in_schema=False)
async def admin_dashboard_savers_cross(request: Request):
    """Tick or untick "blocked by me" for one person. Saves a note, nothing else."""
    from urllib.parse import parse_qs

    from fastapi.responses import RedirectResponse

    from app.db.database import get_connection
    from app.services.heavy_savers import set_crossed

    _admin_or_not_found(request)
    form = parse_qs((await request.body()).decode("utf-8", "replace"))
    user_id = (form.get("user_id") or [""])[0].strip()
    crossed = (form.get("crossed") or [""])[0] == "1"
    if not user_id.startswith("user_ig_"):
        raise HTTPException(status_code=400, detail="Unknown person")
    with get_connection() as connection:
        set_crossed(connection, user_id, crossed)
    return RedirectResponse(f"/admin/dashboard/savers#{user_id}", status_code=303)


@router.get("/dashboard.json", include_in_schema=False)
def admin_dashboard_json(request: Request):
    """The same numbers as data, for a quick look or a future widget."""
    from app.services.admin_stats import dashboard_data

    _admin_or_not_found(request)
    return dashboard_data()


@router.get("/comment-reels", response_class=HTMLResponse, include_in_schema=False)
def admin_comment_reels(request: Request):
    """Reels that say "comment LINK to get the link". No user data."""
    from app.services.comment_bait import list_tagged
    from app.ui_ux.admin_dashboard import render_comment_reels

    _admin_or_not_found(request)
    return HTMLResponse(render_comment_reels(list_tagged()), headers={"Cache-Control": "no-store"})


@router.get("/comment-reels.csv", include_in_schema=False)
def admin_comment_reels_csv(request: Request):
    import csv
    import io

    from fastapi.responses import Response

    from app.services.comment_bait import list_tagged

    _admin_or_not_found(request)
    out = io.StringIO()
    fields = ["reel_id", "title", "url", "trigger", "promise", "source", "snippet", "tagged_at", "saves"]
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in list_tagged():
        writer.writerow({k: row[k] for k in fields})
    return Response(
        out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="comment_reels.csv"', "Cache-Control": "no-store"},
    )


@router.get("/users")
def admin_users(request: Request):
    require_admin(request)
    return {"users": list_users_admin()}


@router.get("/llm-usage")
def admin_llm_usage(request: Request, days: int = Query(default=7, ge=1, le=365)):
    """OpenAI tokens and rupees by call site, from the llm_usage log."""
    require_admin(request)
    return llm_usage_summary(days)


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
    the spot; if not, the redeemed link code and its exact redemption time are
    returned, which locate the thread by date in an inbox that cannot be
    searched by message text.
    """
    require_admin(request)
    return whois(q)
