import csv
import io
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from app.schemas import ReelRecord
from app.services.auth import ensure_user_access, require_user
from app.services.jobs import enqueue_library_rebuild_job, enqueue_reel_job, start_worker_if_needed
from app.services.reel_ingest import (
    delete_reel,
    get_reel_by_id,
    invalidate_user_library_outputs,
    load_reels,
    reset_reel_for_retry,
    reset_user_library,
    user_dashboard_paths,
)


router = APIRouter(prefix="/reels", tags=["reels"])


def _read_csv_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as infile:
        return [dict(row) for row in csv.DictReader(infile)]


@router.get("", response_model=list[ReelRecord])
def list_reels(request: Request, user_id: Optional[str] = Query(default=None)):
    resolved_user_id = ensure_user_access(request, user_id or "")
    return load_reels(user_id=resolved_user_id)


@router.get("/export/urls.txt", response_class=PlainTextResponse)
def export_reel_urls_text(request: Request, user_id: Optional[str] = Query(default=None)):
    resolved_user_id = ensure_user_access(request, user_id or "")
    rows = load_reels(user_id=resolved_user_id)
    body = "\n".join(row["url"] for row in rows if row.get("url")).strip()
    if body:
        body += "\n"
    return PlainTextResponse(
        body,
        headers={
            "Content-Disposition": f'attachment; filename="{resolved_user_id}_reel_urls.txt"',
        },
    )


@router.get("/export/reels.csv")
def export_reels_csv(request: Request, user_id: Optional[str] = Query(default=None)):
    resolved_user_id = ensure_user_access(request, user_id or "")
    rows = load_reels(user_id=resolved_user_id)
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "id",
            "user_id",
            "url",
            "shortcode",
            "received_at",
            "status",
            "media_status",
            "local_video_path",
            "thumbnail_path",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{resolved_user_id}_reels.csv"',
        },
    )


@router.get("/export/raw-output.csv")
def export_raw_output_csv(request: Request, user_id: Optional[str] = Query(default=None)):
    resolved_user_id = ensure_user_access(request, user_id or "")
    raw_output_path = Path(user_dashboard_paths(resolved_user_id)["raw_output"])
    if not raw_output_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw output CSV not found for this user")
    return FileResponse(
        path=str(raw_output_path),
        media_type="text/csv",
        filename=f"{resolved_user_id}_raw_output.csv",
    )


@router.get("/export/accumulated.csv")
def export_accumulated_csv(request: Request, user_id: Optional[str] = Query(default=None)):
    resolved_user_id = ensure_user_access(request, user_id or "")
    accumulated_path = Path(user_dashboard_paths(resolved_user_id)["accumulated_output"])
    if not accumulated_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Accumulated CSV not found for this user")
    return FileResponse(
        path=str(accumulated_path),
        media_type="text/csv",
        filename=f"{resolved_user_id}_accumulated.csv",
    )


@router.get("/export/raw-output.json")
def export_raw_output_json(request: Request, user_id: Optional[str] = Query(default=None)):
    resolved_user_id = ensure_user_access(request, user_id or "")
    raw_output_path = Path(user_dashboard_paths(resolved_user_id)["raw_output"])
    if not raw_output_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw output CSV not found for this user")
    rows = _read_csv_rows(raw_output_path)
    return JSONResponse(
        {
            "user_id": resolved_user_id,
            "kind": "raw_output",
            "row_count": len(rows),
            "rows": rows,
        }
    )


@router.get("/export/accumulated.json")
def export_accumulated_json(request: Request, user_id: Optional[str] = Query(default=None)):
    resolved_user_id = ensure_user_access(request, user_id or "")
    accumulated_path = Path(user_dashboard_paths(resolved_user_id)["accumulated_output"])
    if not accumulated_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Accumulated CSV not found for this user")
    rows = _read_csv_rows(accumulated_path)
    return JSONResponse(
        {
            "user_id": resolved_user_id,
            "kind": "accumulated",
            "row_count": len(rows),
            "rows": rows,
        }
    )


@router.delete("/{reel_id}")
def remove_reel(reel_id: str, request: Request):
    require_user(request)
    reel = get_reel_by_id(reel_id)
    if not reel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reel not found")
    ensure_user_access(request, reel["user_id"])
    deleted = delete_reel(reel_id)
    job = None
    if deleted:
        job = enqueue_library_rebuild_job(reel["user_id"])
        start_worker_if_needed()
    return {
        "ok": deleted,
        "deleted": reel_id,
        "user_id": reel["user_id"],
        "rebuild_job_status": job["status"] if job else "",
    }


@router.post("/reset")
def reset_library(request: Request, user_id: Optional[str] = Query(default=None)):
    resolved_user_id = ensure_user_access(request, user_id or "")
    require_user(request)
    result = reset_user_library(resolved_user_id)
    return {
        "ok": True,
        **result,
    }


@router.post("/rebuild")
def rebuild_library(request: Request, user_id: Optional[str] = Query(default=None)):
    resolved_user_id = ensure_user_access(request, user_id or "")
    require_user(request)
    invalidated = invalidate_user_library_outputs(resolved_user_id)
    job = enqueue_library_rebuild_job(resolved_user_id)
    start_worker_if_needed()
    return {
        "ok": True,
        "user_id": resolved_user_id,
        **invalidated,
        "job_id": job["id"],
        "job_status": job["status"],
        "job_type": job["job_type"],
    }


@router.post("/{reel_id}/retry")
def retry_reel(reel_id: str, request: Request):
    require_user(request)
    reel = get_reel_by_id(reel_id)
    if not reel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reel not found")
    ensure_user_access(request, reel["user_id"])
    reset = reset_reel_for_retry(reel_id)
    job = enqueue_reel_job(reel_id, user_id=reel["user_id"])
    start_worker_if_needed()
    return {
        "ok": True,
        "id": reel_id,
        "user_id": reel["user_id"],
        "status": reset["status"] if reset else "pending",
        "job_status": job["status"],
    }
