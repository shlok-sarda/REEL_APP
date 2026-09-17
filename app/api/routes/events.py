"""Public funnel counters for the landing page, plus an admin read-out.

The write endpoint is intentionally unauthenticated — it is called by visitors
who have no account, which is the entire point of measuring them.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request

from app.services.auth import require_admin
from app.services.events import funnel_summary, record_landing_event

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/landing")
def landing_event(request: Request, payload: dict = Body(default={})):
    """Record one allowlisted landing-page event.

    Always answers 200. A blocked tracker, a bot, or a junk event name should
    look identical to the caller — there is nothing here worth probing, and
    the landing page must not show an error because a counter failed.
    """
    recorded = record_landing_event(
        str(payload.get("event", "")),
        visitor=str(payload.get("visitor", "")),
        source=str(payload.get("source", "")),
    )
    return {"ok": True, "recorded": recorded}


@router.get("/landing/summary")
def landing_summary(days: int = 30, _admin: dict = Depends(require_admin)):
    return funnel_summary(days)
