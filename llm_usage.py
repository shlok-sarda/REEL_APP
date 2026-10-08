"""Token usage log for every OpenAI call made through get_openai_client().

One row per call in the app DB (llm_usage). Nothing here may ever break or
slow the call it is measuring: every step is wrapped, a busy database is
waited on briefly and the row is retried on the next call or at exit.

Attribution comes from two places so call sites need no changes:
  * caller  - the file:function that made the call, read off the stack
  * context - user / reel, set by the pipeline via set_context() and carried
              into child scripts through LLM_USAGE_* environment variables
"""

from __future__ import annotations

import atexit
import json
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve()
_lock = threading.Lock()
_pending: list[tuple] = []
_context = threading.local()
# After a failed write (database busy), wait this long before trying again so
# a held lock costs one short wait, not one per call.
RETRY_AFTER_SECONDS = 30
_retry_at = 0.0

ENV_USER = "LLM_USAGE_USER_ID"
ENV_REEL = "LLM_USAGE_REEL"


def set_context(user_id: str | None = None, reel: str | None = None, inherit: bool = False) -> None:
    """Tag the calls that follow. inherit=True also exports the tag so child
    scripts started from this process carry it."""
    try:
        if user_id is not None:
            _context.user_id = str(user_id)
            if inherit:
                os.environ[ENV_USER] = str(user_id)
        if reel is not None:
            _context.reel = str(reel)
            if inherit:
                os.environ[ENV_REEL] = str(reel)
    except Exception:
        pass


def _current(name: str, env: str) -> str:
    return getattr(_context, name, "") or os.environ.get(env, "")


def _caller() -> str:
    """First frame outside this file and outside the openai package."""
    try:
        frame = sys._getframe(2)
        while frame is not None:
            filename = frame.f_code.co_filename
            if filename != str(_HERE) and "openai" not in Path(filename).parts:
                return f"{Path(filename).name}:{frame.f_code.co_name}"
            frame = frame.f_back
    except Exception:
        pass
    return ""


def _plain(usage) -> dict:
    if usage is None:
        return {}
    for attr in ("model_dump", "dict"):
        try:
            return getattr(usage, attr)()
        except Exception:
            continue
    return dict(usage) if isinstance(usage, dict) else {}


def _row(kind: str, model: str, usage: dict, caller: str) -> tuple:
    details = usage.get("prompt_tokens_details") or usage.get("input_token_details") or {}
    prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
    completion = usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
    return (
        datetime.now(timezone.utc).isoformat(),
        _current("user_id", ENV_USER),
        _current("reel", ENV_REEL),
        Path(sys.argv[0] or "").name,
        caller,
        kind,
        model,
        int(prompt),
        int(completion),
        int(details.get("cached_tokens", 0) or 0),
        int(details.get("audio_tokens", 0) or 0),
        float(usage.get("seconds", 0) or 0),
        json.dumps(usage, default=str)[:2000],
    )


def _flush(timeout: float) -> None:
    with _lock:
        if not _pending:
            return
        rows = list(_pending)
        from app.config import settings

        connection = sqlite3.connect(settings.database_path, timeout=timeout)
        try:
            connection.executemany(
                """
                INSERT INTO llm_usage (
                    created_at, user_id, reel, script, caller, kind, model,
                    prompt_tokens, completion_tokens, cached_tokens, audio_tokens,
                    audio_seconds, usage_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.commit()
            del _pending[: len(rows)]
        finally:
            connection.close()


def record(kind: str, model: str, response, caller: str = "") -> None:
    try:
        usage = _plain(getattr(response, "usage", None))
        if not usage:
            return
        with _lock:
            # Bounded: if the table is unreachable for a whole run, drop the
            # oldest rows rather than grow without limit.
            if len(_pending) >= 500:
                del _pending[0]
            _pending.append(_row(kind, str(model or ""), usage, caller))
    except Exception:
        return
    global _retry_at
    if time.monotonic() < _retry_at:
        return
    try:
        _flush(timeout=1)
    except Exception:
        _retry_at = time.monotonic() + RETRY_AFTER_SECONDS


def _flush_at_exit() -> None:
    try:
        _flush(timeout=10)
    except Exception:
        pass


atexit.register(_flush_at_exit)


def _wrap(resource, kind: str) -> None:
    original = resource.create

    def create(*args, **kwargs):
        response = original(*args, **kwargs)
        try:
            record(kind, kwargs.get("model", ""), response, _caller())
        except Exception:
            pass
        return response

    resource.create = create


def instrument(client):
    """Make a client log its chat, embedding and transcription calls."""
    for path, kind in (
        (("chat", "completions"), "chat"),
        (("embeddings",), "embedding"),
        (("audio", "transcriptions"), "transcription"),
    ):
        try:
            resource = client
            for name in path:
                resource = getattr(resource, name)
            _wrap(resource, kind)
        except Exception:
            pass
    return client
