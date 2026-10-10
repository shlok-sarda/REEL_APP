import secrets as _secrets

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.schemas import HealthResponse
from app.services.reel_ingest import ensure_storage


router = APIRouter(tags=["health"])


def _queue_snapshot() -> dict:
    # Raw counts only — deliberately no janitor/recovery side effects here,
    # since health checks may be polled frequently.
    try:
        from app.db.database import get_connection

        with get_connection() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS n FROM processing_jobs GROUP BY status"
            ).fetchall()
        return {row["status"]: row["n"] for row in rows}
    except Exception:
        return {}


def _queue_debug(full: bool = False) -> dict:
def _config_summary() -> dict:
    """Which switches are on, for checking the host's settings with one curl.

    Public, so it carries yes/no answers and non-secret names only. Never a
    key, token or secret value.
    """
    import os

    def _flag(name: str) -> bool:
        return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}

    # Same parsing as finale.py, which is too heavy to import here.
    try:
        keyframe_max_edge = int(os.getenv("KEYFRAME_MAX_EDGE", "").strip() or 512)
    except ValueError:
        keyframe_max_edge = 512
    return {
        "app_env": settings.app_env,
        "openai_key_set": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "apify_configured": bool(settings.apify_token),
        "instagram_app_secret_set": bool(settings.instagram_app_secret),
        "session_secret_default": settings.session_secret.strip() in {"", "change-me-before-launch"},
        "extraction_model": os.getenv("EXTRACTION_MODEL", "").strip() or "gpt-4.1-mini",
        "keyframe_max_edge": keyframe_max_edge,
        "outbound_dm_test": settings.outbound_dm_test,
        "guest_autocreate_for_everyone": settings.guest_autocreate_for_everyone,
        "dm_reply_for_everyone": settings.dm_reply_for_everyone,
        "app_v2_for_everyone": settings.app_v2_for_everyone,
        "collections_for_everyone": settings.collections_for_everyone,
        "guest_lock_enabled": settings.guest_lock_enabled,
        "queue_janitor": os.getenv("QUEUE_JANITOR", "on").strip().lower() != "off",
    }


    """Read-only view of the recovery machinery's inputs, for remote triage.

    The default (public) view carries only operational vitals safe for an
    unauthenticated endpoint. full=True adds worker/job forensics — including
    other users' reel ids and error text — so it requires the debug token.
    """
    import os
    import time
    from datetime import datetime

    info: dict = {
        "git_commit": os.getenv("RENDER_GIT_COMMIT", "")[:10],
        "server_now": datetime.now().isoformat(timespec="seconds"),
        "processor_timeout_seconds": settings.processor_timeout_seconds,
    }
    try:
        import shutil

        usage = shutil.disk_usage(settings.storage_dir)
        info["disk"] = {
            "total_mb": usage.total // (1024 * 1024),
            "free_mb": usage.free // (1024 * 1024),
        }
        # Distinguish "disk full" from other write failures directly.
        from app.db.database import get_connection

        with get_connection() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS write_probe (id INTEGER PRIMARY KEY, ts TEXT)"
            )
            connection.execute("DELETE FROM write_probe")
            connection.execute("INSERT INTO write_probe (ts) VALUES (?)", (info["server_now"],))
        info["db_writable"] = True
    except Exception as exc:
        info["db_writable"] = False
        info["db_write_error"] = str(exc)[:200]
    try:
        from app.services.jobs import openai_pause_until

        pause = openai_pause_until()
        if pause:
            info["openai_paused_until"] = pause
    except Exception:
        pass
    if not full:
    info["config"] = _config_summary()
    try:
        from app.services.db_backup import last_backup_at

        info["db_backup_last"] = last_backup_at()
    except Exception:
        info["db_backup_last"] = ""
        return info
    try:
        from app.services.jobs import _pid_is_worker, _stale_cutoff_for

        info["stale_cutoff_process_reel"] = _stale_cutoff_for("process_reel")
        lock = settings.worker_lock_file
        if lock.exists():
            entry: dict = {"exists": True}
            try:
                entry["age_seconds"] = int(time.time() - lock.stat().st_mtime)
                pid = int(lock.read_text().strip())
                entry["pid"] = pid
                entry["pid_is_worker"] = _pid_is_worker(pid)
            except Exception as exc:
                entry["error"] = str(exc)[:120]
            info["worker_lock"] = entry
        else:
            info["worker_lock"] = {"exists": False}
        from app.db.database import get_connection

        with get_connection() as connection:
            rows = connection.execute(
                "SELECT job_type, started_at FROM processing_jobs WHERE status = 'running' ORDER BY id DESC LIMIT 25"
            ).fetchall()
            reel_columns = [
                row["name"] for row in connection.execute("PRAGMA table_info(reels)").fetchall()
            ]
        info["running_started_at"] = [f"{row['job_type']}:{row['started_at']}" for row in rows]
        info["reels_columns"] = reel_columns
        with get_connection() as connection:
            failure_rows = connection.execute(
                """
                SELECT reel_id, error_message, finished_at
                FROM processing_jobs
                WHERE status = 'failed'
                ORDER BY id DESC
                LIMIT 8
                """
            ).fetchall()
        info["recent_failures"] = [
            f"{row['finished_at']} {row['reel_id']}: {row['error_message'] or ''}"
            for row in failure_rows
        ]
    except Exception as exc:
        info["error"] = str(exc)[:200]
    return info


def _run_inline_fix() -> dict:
    """Run queue recovery in-request and report exactly what happened.

    Remote triage tool: the janitor's failures are only visible in server
    logs, so this exposes each stage's rowcount/exception in the response.
    Everything here is idempotent maintenance the janitor already attempts.
    """
    import subprocess
    import sys
    import time
    from datetime import datetime, timedelta

    report: dict = {}
    from app.db.database import get_connection

    try:
        from app.services.jobs import is_worker_running

        report["worker_alive"] = is_worker_running()
    except Exception as exc:
        report["worker_alive_error"] = repr(exc)[:300]
    # Stage 1: the real service-path recovery, with its error surfaced.
    try:
        from app.services.jobs import recover_orphaned_jobs

        report["service_recovered"] = recover_orphaned_jobs()
    except Exception as exc:
        report["service_recover_error"] = repr(exc)[:300]
    # Stage 2: raw fallback requeue — stale claims only, so a live worker's
    # in-flight job is never yanked into double processing.
    try:
        stale_cutoff = (datetime.now() - timedelta(seconds=1500)).isoformat(timespec="seconds")
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE processing_jobs
                SET status = 'pending', started_at = ''
                WHERE status = 'running'
                  AND started_at < ?
                """,
                (stale_cutoff,),
            )
            report["raw_requeued_stale"] = cursor.rowcount
    except Exception as exc:
        report["raw_requeue_error"] = repr(exc)[:300]
    # Stage 3: run the real worker synchronously with output captured. If it
    # crashes before creating its lock we finally see the traceback; if it's
    # healthy we see it claim a job (the 25s kill orphans that claim, which
    # stale recovery requeues — acceptable for a manual diagnostic).
    try:
        repo_root = settings.worker_script.parent.parent.parent
        try:
            probe = subprocess.run(
                [sys.executable, str(settings.worker_script)],
                capture_output=True,
                text=True,
                timeout=25,
                cwd=str(repo_root),
            )
            output = (probe.stdout or "") + "\n" + (probe.stderr or "")
            report["worker_run"] = f"exit={probe.returncode} {output[-600:].strip()}"
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or b"", exc.stderr or b"")
            text_out = " ".join(
                part.decode("utf-8", "replace") if isinstance(part, bytes) else part for part in out
            )
            report["worker_run"] = f"still_running_at_25s {text_out[-600:].strip()}"
    except Exception as exc:
        report["worker_run_error"] = repr(exc)[:300]
    # Stage 3.5: is the OpenAI key alive and funded? A dead key/quota makes
    # every reel fail at the first step that calls the API. One 1-token
    # embedding per manual fix=1 invocation — negligible cost.
    try:
        import os as _os

        from openai import OpenAI

        _key = _os.getenv("OPENAI_API_KEY", "").strip()
        if not _key:
            report["openai_probe"] = "NO KEY IN ENV"
        else:
            _client = OpenAI(api_key=_key, timeout=20, max_retries=0)
            _client.embeddings.create(model="text-embedding-3-small", input="ping")
            report["openai_probe"] = "ok — paid call accepted"
    except Exception as exc:
        report["openai_probe"] = f"FAILED: {exc}"[:300]
    # Stage 4: kick the janitor, give a spawned worker a moment, then inspect.
    try:
        from app.services.jobs import ensure_background_progress

        ensure_background_progress()
        report["ensure_background_progress"] = "ok"
    except Exception as exc:
        report["ensure_error"] = repr(exc)[:300]
    time.sleep(3)
    try:
        report["lock_after"] = settings.worker_lock_file.exists()
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS n FROM processing_jobs GROUP BY status"
            ).fetchall()
        report["queue_after"] = {row["status"]: row["n"] for row in rows}
    except Exception as exc:
        report["queue_after_error"] = repr(exc)[:300]
    return report


def _debug_authorized(token: str) -> bool:
    # Reuses the ingest secret so no new env var is needed. Fails closed when
    # the secret is unset — the full debug view stays off rather than open.
    secret = settings.telegram_ingest_secret
    return bool(secret) and _secrets.compare_digest(token.strip(), secret)


def _instagram_webhook_debug(limit: int = 15) -> dict:
    """Recent webhook rows, for diagnosing why an expected DM did nothing.

    Token-gated with the rest of the full view. Sender ids are truncated: the
    triage question is which senders are distinct and whether a reply was
    attempted, never who they are.
    """
    from app.db.database import get_connection

    import os as _os

    out: dict = {"sending_enabled": bool(settings.instagram_access_token)}
    # Expiry, last refresh and whether Meta has rejected the token. "ok": false
    # here means DMs are failing or about to.
    try:
        from app.services.instagram_token import status as _token_status

        out["token"] = _token_status()
    except Exception as exc:
        out["token"] = {"ok": False, "reason": f"status_failed: {exc}"[:200]}
    out["outbound_dm_test"] = settings.outbound_dm_test
    out["graph_version"] = settings.instagram_graph_version
    # A library link is only useful if it is absolute. An unset PUBLIC_BASE_URL
    # silently produces "/g/<token>", which is unopenable from a DM.
    out["public_base_url"] = settings.public_base_url
    # Names and lengths only, never values. Distinguishes "never set" from
    # "set under a slightly different name" — the two look identical from
    # inside the app, and only one of them is fixed by pasting a new token.
    # The switches that decide whether anything is sent at all. Not secrets,
    # and a typo in one of them is otherwise indistinguishable from the
    # feature being broken.
    out["guest_test_senders"] = sorted(settings.guest_test_senders)
    out["dm_reply_accounts"] = sorted(settings.dm_reply_accounts)
    out["dm_reply_for_everyone"] = settings.dm_reply_for_everyone
    out["guest_autocreate_for_everyone"] = settings.guest_autocreate_for_everyone
    out["guest_lock_enabled"] = settings.guest_lock_enabled
    out["dm_cooldown_minutes"] = settings.dm_cooldown_minutes
    # Launch scoreboard. Guest accounts are the number the reels are judged
    # on: a stranger's first DM made an account (created), and a Google
    # sign-in kept it (signed_in). Timestamps are ISO text, so compare on a
    # normalised "YYYY-MM-DD HH:MM:SS" prefix against SQLite's UTC clock.
    try:
        with get_connection() as connection:
            g = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN substr(replace(created_at, 'T', ' '), 1, 19) >= datetime('now', '-1 day') THEN 1 ELSE 0 END) AS last_24h,
                       SUM(CASE WHEN substr(replace(created_at, 'T', ' '), 1, 19) >= datetime('now', '-7 days') THEN 1 ELSE 0 END) AS last_7d,
                       SUM(CASE WHEN COALESCE(google_sub, '') <> '' THEN 1 ELSE 0 END) AS signed_in
                FROM users
                WHERE id LIKE 'user_ig_%'
                """
            ).fetchone()
        out["guests"] = {k: int(g[k] or 0) for k in ("total", "last_24h", "last_7d", "signed_in")}
    except Exception as exc:
        out["guests_error"] = str(exc)[:200]
    out["env_names_seen"] = sorted(
        f"{k}(len={len(v.strip())})"
        for k, v in _os.environ.items()
        if "INSTAGRAM" in k.upper() or "IG_" in k.upper()
    )
    try:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT received_at, kind, sender_id, sender_username, outcome, detail
                FROM instagram_webhook_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out["events"] = [
            {
                "at": r["received_at"],
                "kind": r["kind"],
                "sender": ("..." + str(r["sender_id"])[-6:]) if r["sender_id"] else "",
                "username": r["sender_username"],
                "outcome": r["outcome"],
                "detail": (r["detail"] or "")[:220],
            }
            for r in rows
        ]
    except Exception as exc:
        out["events_error"] = str(exc)[:200]
    return out


# Every table keyed to a user. Derived by introspecting the built schema
# rather than by memory, so a table added later and forgotten here shows up
# as a leftover rather than silently surviving a reset.
_USER_SCOPED_TABLES = [
    "cluster_events", "cluster_memberships", "deep_search_documents",
    "folder_adjudications", "folder_memberships", "instagram_link_tokens",
    "nudge_log", "processing_jobs", "reel_item_features", "reel_locations",
    "reel_processing_diagnostics", "reel_recipes", "reels",
    "report_events", "search_reports", "telegram_link_tokens", "user_folders", "user_interest_edges",
    "user_interest_nodes",
]


def _reset_test_guest(handle: str) -> dict:
    """Wipe a test guest so the funnel can be replayed from the beginning.

    Exists because the first-contact message and the "1 of 5" frame fire once
    per account ever, so testing the new-user experience otherwise costs a
    fresh Instagram account every run.

    Refuses anything not named in GUEST_TEST_SENDERS, and refuses any account
    that has ever signed in with Google. A real user must not be reachable
    from here by any spelling.
    """
    from app.db.database import get_connection
    from app.services import nudge

    wanted = (handle or "").strip().lower().lstrip("@")
    if not wanted:
        return {"ok": False, "error": "no handle given"}
    if not nudge.sender_allowed(wanted, wanted):
        return {"ok": False, "error": f"{wanted!r} is not in GUEST_TEST_SENDERS"}

    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, google_sub, instagram_user_id, instagram_username FROM users "
            "WHERE lower(instagram_username) = ? OR instagram_user_id = ? LIMIT 1",
            (wanted, wanted),
        ).fetchone()
        if not row:
            return {"ok": True, "note": f"no account for {wanted!r}, nothing to reset"}
        if (row["google_sub"] or "").strip():
            return {"ok": False, "error": "account has signed in with Google, refusing"}

        user_id = row["id"]
        reel_ids = [r["id"] for r in connection.execute(
            "SELECT id FROM reels WHERE user_id = ?", (user_id,))]
        deleted = {}
        if reel_ids:
            marks = ",".join("?" * len(reel_ids))
            cur = connection.execute(
                f"DELETE FROM reel_items WHERE reel_id IN ({marks})", reel_ids)
            deleted["reel_items"] = cur.rowcount
        for table in _USER_SCOPED_TABLES:
            try:
                cur = connection.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
                if cur.rowcount:
                    deleted[table] = cur.rowcount
            except Exception as exc:
                deleted[f"{table}_error"] = str(exc)[:80]
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        deleted["users"] = 1

    return {
        "ok": True,
        "reset": wanted,
        "user_id": user_id,
        "deleted": deleted,
        "note": "account removed; the next DM recreates it and the funnel starts at message one",
    }


@router.get("/health", response_model=HealthResponse)
def health_check(fix: int = 0, token: str = "", reset_guest: str = ""):
    ensure_storage()
    authorized = _debug_authorized(token)
    if fix and not authorized:
        # fix=1 runs heavy recovery (25s synchronous worker probe, a paid
        # OpenAI call) — not something the open internet gets to trigger.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Debug token required")
    debug = _queue_debug(full=authorized)
    if authorized:
        debug["instagram_webhook"] = _instagram_webhook_debug()
    if fix:
        debug["fix_report"] = _run_inline_fix()
    if reset_guest:
        if not authorized:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Debug token required")
        debug["reset_guest"] = _reset_test_guest(reset_guest)
    return HealthResponse(
        service="reel-organizer-api",
        endpoint="/instagram/webhook",
        environment=settings.app_env,
        storage_dir=str(settings.storage_dir),
        media_dir=str(settings.media_dir),
        csv_file=str(settings.reel_urls_csv),
        media_storage_mode="r2+local_cache" if settings.r2_enabled else "local_only",
        r2_enabled=settings.r2_enabled,
        queue=_queue_snapshot(),
        queue_debug=debug,
    )
