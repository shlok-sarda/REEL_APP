import os

from openai import OpenAI


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable")
    return OpenAI(api_key=api_key)
