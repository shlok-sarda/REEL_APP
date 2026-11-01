"""Send the app's chat calls to Claude without touching the call sites.

Every text call in the app is written as client.chat.completions.create(...)
in OpenAI's shape. When ANTHROPIC_API_KEY is set, get_openai_client() hands
back a ClaudeChatClient instead: chat calls are translated to the Claude
Messages API and the answer is handed back in the same shape the callers
already read (choices[0].message.content, usage.prompt_tokens, stream deltas).

Things Claude has no API for (embeddings, voice transcription, icon images)
still go to OpenAI, as before.

If a Claude call fails for any reason (out of credit, outage, a request this
file translated badly) and an OpenAI key is set, the same call is retried on
OpenAI so users keep getting answers. LLM_PROVIDER=openai switches Claude off
entirely without a deploy of new code.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from typing import Any, Callable, Iterator

# gpt-4.1-mini / nano did the cheap work, gpt-4.1 the harder routing. The
# cheap work goes to Haiku, everything else to Sonnet. Both overridable.
FAST_MODEL = os.getenv("CLAUDE_FAST_MODEL", "").strip() or "claude-haiku-5-5"
STRONG_MODEL = os.getenv("CLAUDE_STRONG_MODEL", "").strip() or "claude-sonnet-5-5"

JSON_ONLY = (
    "Reply with exactly one valid JSON object and nothing else: "
    "no code fences, no text before or after it."
)

# OpenAI let a call run without a cap. Claude needs one; this is far above
# what any call here writes, and a call stops when it is done, not at the cap.
DEFAULT_MAX_TOKENS = 16000
# A tiny cap (folders asks for 20) leaves no room if Claude adds a space or a
# newline around the JSON. It still stops as soon as the answer is written.
MIN_MAX_TOKENS = 200


def claude_enabled() -> bool:
    if os.getenv("LLM_PROVIDER", "").strip().lower() == "openai":
        return False
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


def claude_model_for(openai_model: str) -> str:
    name = (openai_model or "").lower()
    if name.startswith("claude"):
        return openai_model
    if "mini" in name or "nano" in name or not name:
        return FAST_MODEL
    return STRONG_MODEL


# ------------------------------------------------------------ requests ---

def _image_block(part: dict) -> dict | None:
    url = str((part.get("image_url") or {}).get("url") or "")
    if url.startswith("data:") and ";base64," in url:
        head, data = url.split(";base64,", 1)
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": head[5:] or "image/jpeg", "data": data},
        }
    if url.startswith("http"):
        return {"type": "image", "source": {"type": "url", "url": url}}
    return None


def _content(content: Any) -> Any:
    if isinstance(content, str) or content is None:
        return content or ""
    blocks = []
    for part in content:
        kind = part.get("type")
        if kind == "text":
            blocks.append({"type": "text", "text": part.get("text") or ""})
        elif kind == "image_url":
            block = _image_block(part)
            if block:
                blocks.append(block)
    return blocks


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(p.get("text") or "" for p in (content or []) if p.get("type") == "text")


def build_request(kwargs: dict) -> tuple[dict, bool]:
    """OpenAI chat.completions kwargs -> (Claude messages.create kwargs, json mode)."""
    system_parts: list[str] = []
    messages = []
    for message in kwargs.get("messages") or []:
        role = message.get("role")
        if role in ("system", "developer"):
            system_parts.append(_text_of(message.get("content")))
        else:
            messages.append({"role": "assistant" if role == "assistant" else "user",
                             "content": _content(message.get("content"))})
    json_mode = (kwargs.get("response_format") or {}).get("type") in ("json_object", "json_schema")
    if json_mode:
        system_parts.append(JSON_ONLY)

    model = claude_model_for(str(kwargs.get("model") or ""))
    cap = kwargs.get("max_completion_tokens") or kwargs.get("max_tokens") or DEFAULT_MAX_TOKENS
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": max(int(cap), MIN_MAX_TOKENS),
        "messages": messages,
    }
    if system_parts:
        request["system"] = "\n\n".join(p for p in system_parts if p)
    # The gpt-4.1 models never thought before answering. Keep it that way:
    # same behaviour, and no thinking tokens on the bill. Current Claude
    # models refuse temperature/seed, so those are dropped.
    if model == "claude-sonnet-5-5":
        request["thinking"] = {"type": "between_tools"}
    elif model == "claude-haiku-5-5":
        request["thinking"] = {"type": "disabled"}
    return request, json_mode


# ----------------------------------------------------------- responses ---

class _Usage:
    def __init__(self, usage: Any):
        fresh = int(getattr(usage, "input_tokens", 0) or 0)
        read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        self.prompt_tokens = fresh + read + write
        self.completion_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        self.total_tokens = self.prompt_tokens + self.completion_tokens
        self.prompt_tokens_details = {"cached_tokens": read}

    def model_dump(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "prompt_tokens_details": dict(self.prompt_tokens_details),
            "provider": "anthropic",
        }


def clean_json_text(text: str) -> str:
    """Cut anything around the outermost {...} (a code fence, a stray word)."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        return text.strip()
    return text[start:end + 1]


_FINISH = {"end_turn": "stop", "stop_sequence": "stop", "max_tokens": "length"}


def _completion(message: Any, json_mode: bool) -> SimpleNamespace:
    text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
    if json_mode:
        text = clean_json_text(text)
    return SimpleNamespace(
        id=message.id,
        model=message.model,
        choices=[SimpleNamespace(
            index=0,
            message=SimpleNamespace(role="assistant", content=text),
            finish_reason=_FINISH.get(message.stop_reason or "", message.stop_reason),
        )],
        usage=_Usage(message.usage),
    )


def _chunk(text: str | None = None, usage: _Usage | None = None, model: str = "") -> SimpleNamespace:
    choices = [] if text is None else [SimpleNamespace(index=0, delta=SimpleNamespace(content=text), finish_reason=None)]
    return SimpleNamespace(model=model, choices=choices, usage=usage)


def _stream(client: Any, request: dict, json_mode: bool, include_usage: bool) -> Iterator[SimpleNamespace]:
    model = request["model"]
    with client.messages.stream(**request) as stream:
        if not json_mode:
            for text in stream.text_stream:
                yield _chunk(text, model=model)
        else:
            # Hold back anything before the first "{" and after the latest "}"
            # so a code fence never reaches a caller that parses as it goes.
            seen, sent = "", 0
            for text in stream.text_stream:
                seen += text
                start, end = seen.find("{"), seen.rfind("}")
                if start == -1:
                    continue
                sent = max(sent, start)
                if end + 1 > sent:
                    yield _chunk(seen[sent:end + 1], model=model)
                    sent = end + 1
        final = stream.get_final_message()
    if include_usage:
        yield _chunk(None, usage=_Usage(final.usage), model=model)


# -------------------------------------------------------------- client ---

def _warn(message: str) -> None:
    try:
        print(f"[claude] {message}", file=sys.stderr, flush=True)
    except Exception:
        pass


class InvalidAnswer(Exception):
    pass


class _Completions:
    def __init__(self, owner: "ClaudeChatClient"):
        self._owner = owner

    def create(self, *args: Any, **kwargs: Any) -> Any:
        import anthropic

        request, json_mode = build_request(kwargs)
        try:
            if kwargs.get("stream"):
                include_usage = bool((kwargs.get("stream_options") or {}).get("include_usage"))
                stream = _stream(self._owner.anthropic, request, json_mode, include_usage)
                # Pull the first piece now, so a failed call (no credit, bad
                # request) falls back here instead of inside the caller's loop.
                first = next(stream, None)
                return self._replay(first, stream)
            return self._complete(request, json_mode)
        except (anthropic.APIError, InvalidAnswer) as exc:
            fallback = self._owner.openai_or_none()
            if fallback is None:
                raise
            _warn(f"{request['model']} failed, answering with OpenAI instead: {str(exc)[:300]}")
            return fallback.chat.completions.create(*args, **kwargs)

    def _complete(self, request: dict, json_mode: bool) -> Any:
        """OpenAI's JSON mode promised valid JSON. Claude's plain answer can be
        broken now and then (a stray quote, a refusal, cut off at the cap), and
        callers fail the whole reel on that, so ask once more before giving up."""
        problem = ""
        for _ in range(2):
            completion = _completion(self._owner.anthropic.messages.create(**request), json_mode)
            if not json_mode:
                return completion
            try:
                json.loads(completion.choices[0].message.content)
                return completion
            except ValueError:
                problem = f"not valid JSON (finish: {completion.choices[0].finish_reason})"
        raise InvalidAnswer(problem)

    @staticmethod
    def _replay(first: Any, rest: Iterator[Any]) -> Iterator[Any]:
        if first is not None:
            yield first
        yield from rest


class ClaudeChatClient:
    """Looks like an OpenAI client. Chat goes to Claude, the rest to OpenAI."""

    def __init__(self, openai_factory: Callable[[], Any], timeout: float):
        import anthropic

        self.anthropic = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(), timeout=timeout
        )
        self._openai_factory = openai_factory
        self._openai: Any = None
        self.chat = SimpleNamespace(completions=_Completions(self))

    def openai(self) -> Any:
        if self._openai is None:
            self._openai = self._openai_factory()
        return self._openai

    def openai_or_none(self) -> Any:
        if not os.getenv("OPENAI_API_KEY", "").strip():
            return None
        try:
            return self.openai()
        except Exception:
            return None

    # Embeddings, voice transcription, images, models: OpenAI only.
    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.openai(), name)
