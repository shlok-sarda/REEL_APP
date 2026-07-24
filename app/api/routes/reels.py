import csv
import io
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from app.schemas import ReelRecord
from app.services.auth import block_demo_link_writes, ensure_user_access, require_user
from app.services.jobs import enqueue_library_rebuild_job, enqueue_reel_job, ensure_background_progress
from app.services.reel_ingest import (
    delete_reel,
    get_reel_by_id,
    invalidate_user_library_outputs,
    load_reel_processing_diagnostics,
    load_reels,
    reset_reel_for_retry,
    reset_user_library,
    user_dashboard_paths,
)


router = APIRouter(prefix="/reels", tags=["reels"])

GENERIC_CATEGORY_LABELS = ("", "generic", "miscellaneous", "uncertain", "general", "unsorted")


@router.post("/retry-unsorted")
def retry_unsorted_reels(
    request: Request,
    user_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    dry_run: bool = Query(default=False),
):
    """Repair pass: requeue every reel whose extraction is broken or incomplete.

    Catches: failed reels, reels with no items at all, generic/unsorted
    categories, half-extracted reels (no non-empty item name anywhere, or the
    pipeline's "could not be processed" placeholder summary), and completed
    reels missing their deep-search document. dry_run=1 returns the count
    without requeuing, so the UI can confirm before spending reprocess money."""
    block_demo_link_writes(request, "re-run processing")
    resolved_user_id = ensure_user_access(request, user_id or "")
    placeholders = ",".join("?" for _ in GENERIC_CATEGORY_LABELS)
    from app.db.database import get_connection

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT DISTINCT r.id
            FROM reels r
            LEFT JOIN reel_items ri ON ri.reel_id = r.id
            WHERE r.user_id = ?
              AND r.status != 'pending'
              AND (
                r.status = 'failed'
                OR ri.id IS NULL
                OR LOWER(TRIM(ri.primary_category)) IN ({placeholders})
                OR NOT EXISTS (
                    SELECT 1 FROM reel_items ri2
                    WHERE ri2.reel_id = r.id AND TRIM(ri2.item_name) != ''
                )
                OR LOWER(ri.summary) LIKE '%could not be processed%'
                OR ri.summary LIKE 'Processing error:%'
                OR NOT EXISTS (
                    SELECT 1 FROM deep_search_documents d WHERE d.reel_id = r.id
                )
              )
            ORDER BY r.received_at DESC
            LIMIT ?
            """,
            (resolved_user_id, *GENERIC_CATEGORY_LABELS, limit),
        ).fetchall()
    if dry_run:
        return {
            "ok": True,
            "user_id": resolved_user_id,
            "dry_run": True,
            "broken_count": len(rows),
            "reel_ids": [row["id"] for row in rows[:20]],
        }
    requeued = []
    errors = []
    for row in rows:
        reel_id = row["id"]
        try:
            reset_reel_for_retry(reel_id)
            job = enqueue_reel_job(reel_id, user_id=resolved_user_id)
            requeued.append({"id": reel_id, "job_status": job["status"]})
        except Exception as exc:
            errors.append({"id": reel_id, "error": str(exc)[:200]})
    if requeued:
        ensure_background_progress()
    return {
        "ok": True,
        "user_id": resolved_user_id,
        "requeued_count": len(requeued),
        "error_count": len(errors),
        "errors": errors[:10],
    }


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


@router.get("/export/diagnostics.json")
def export_diagnostics_json(request: Request, user_id: Optional[str] = Query(default=None)):
    resolved_user_id = ensure_user_access(request, user_id or "")
    rows = load_reel_processing_diagnostics(user_id=resolved_user_id)
    return JSONResponse(
        {
            "user_id": resolved_user_id,
            "kind": "diagnostics",
            "row_count": len(rows),
            "rows": rows,
        }
    )


@router.delete("/{reel_id}")
def remove_reel(reel_id: str, request: Request):
    block_demo_link_writes(request, "delete reels")
    require_user(request)
    reel = get_reel_by_id(reel_id)
    if not reel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reel not found")
    ensure_user_access(request, reel["user_id"])
    deleted = delete_reel(reel_id)
    job = None
    if deleted:
        job = enqueue_library_rebuild_job(reel["user_id"])
        ensure_background_progress()
    return {
        "ok": deleted,
        "deleted": reel_id,
        "user_id": reel["user_id"],
        "rebuild_job_status": job["status"] if job else "",
    }


@router.post("/reset")
def reset_library(request: Request, user_id: Optional[str] = Query(default=None)):
    block_demo_link_writes(request, "reset the library")
    resolved_user_id = ensure_user_access(request, user_id or "")
    require_user(request)
    result = reset_user_library(resolved_user_id)
    return {
        "ok": True,
        **result,
    }


@router.post("/rebuild")
def rebuild_library(request: Request, user_id: Optional[str] = Query(default=None)):
    block_demo_link_writes(request, "rebuild the library")
    resolved_user_id = ensure_user_access(request, user_id or "")
    require_user(request)
    invalidated = invalidate_user_library_outputs(resolved_user_id)
    job = enqueue_library_rebuild_job(resolved_user_id)
    ensure_background_progress()
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
    block_demo_link_writes(request, "re-run processing")
    require_user(request)
    reel = get_reel_by_id(reel_id)
    if not reel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reel not found")
    ensure_user_access(request, reel["user_id"])
    reset = reset_reel_for_retry(reel_id)
    job = enqueue_reel_job(reel_id, user_id=reel["user_id"])
    ensure_background_progress()
    return {
        "ok": True,
        "id": reel_id,
        "user_id": reel["user_id"],
        "status": reset["status"] if reset else "pending",
        "job_status": job["status"],
    }
