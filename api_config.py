import os

from openai import OpenAI


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable")
    # The library's own default is a 10 minute wait per call, tried three
    # times. A stalled OpenAI then held a page thread (or the one reel worker)
    # for up to half an hour. Two minutes is far longer than any call here
    # takes when things are working.
    client = OpenAI(api_key=api_key, timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "120")))
    try:
        from llm_usage import instrument

        instrument(client)
    except Exception:
        pass
    return client
