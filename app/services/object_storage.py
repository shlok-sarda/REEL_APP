from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import boto3

from app.config import settings


def _normalized_endpoint() -> str:
    endpoint = settings.r2_endpoint.strip()
    if endpoint and not endpoint.startswith(("http://", "https://")):
        endpoint = f"https://{endpoint}"
    return endpoint.rstrip("/")


@lru_cache(maxsize=1)
def _r2_client():
    if not settings.r2_enabled:
        return None
    return boto3.client(
        "s3",
        endpoint_url=_normalized_endpoint(),
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def r2_is_enabled() -> bool:
    return settings.r2_enabled and _r2_client() is not None


def upload_file(local_path: Path, object_key: str, content_type: str | None = None) -> bool:
    client = _r2_client()
    if client is None or not local_path.exists():
        return False

    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type

    client.upload_file(str(local_path), settings.r2_bucket_name, object_key, ExtraArgs=extra_args)
    return True


def presigned_get_url(object_key: str, expires_in: int = 3600) -> str:
    client = _r2_client()
    if client is None:
        return ""
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": object_key},
        ExpiresIn=expires_in,
    )


def infer_object_key(path_value: str) -> str:
    value = (path_value or "").strip()
    if not value:
        return ""

    parsed = urlparse(value)
    basename = Path(parsed.path).name if parsed.scheme else Path(value).name
    if not basename:
        return ""

    suffix = Path(basename).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return f"thumbnails/{basename}"
    return f"videos/{basename}"
