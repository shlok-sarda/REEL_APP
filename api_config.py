import os

from openai import OpenAI


def _instrument(client):
    try:
        from llm_usage import instrument

        instrument(client)
    except Exception:
        pass
    return client


def _timeout() -> float:
    # The library's own default is a 10 minute wait per call, tried three
    # times. A stalled provider then held a page thread (or the one reel
    # worker) for up to half an hour. Two minutes is far longer than any call
    # here takes when things are working.
    return float(os.getenv("OPENAI_TIMEOUT_SECONDS", "120"))


def _openai_client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable")
    return _instrument(OpenAI(api_key=api_key, timeout=_timeout()))


def get_openai_client():
    """The app's one LLM client. With ANTHROPIC_API_KEY set, chat calls go to
    Claude (see claude_adapter.py) and only embeddings, transcription and
    images still use OpenAI. Without it, this is the plain OpenAI client."""
    from claude_adapter import ClaudeChatClient, claude_enabled

    if claude_enabled():
        client = ClaudeChatClient(_openai_client, timeout=_timeout())
        try:
            from llm_usage import _wrap

            _wrap(client.chat.completions, "chat")
        except Exception:
            pass
        return client
    return _openai_client()
