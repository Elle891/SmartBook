"""
Invoice image storage — S3 with in-memory fallback for tests/dev.
"""

from __future__ import annotations

import os
from typing import Any

_MEMORY_STORE: dict[str, bytes] = {}


def _use_memory() -> bool:
    return os.getenv("INVOICE_STORAGE_BACKEND", "").lower() in ("memory", "test") or not os.getenv(
        "S3_BUCKET"
    )


def build_image_key(account_set_id: str, job_id: str, filename: str) -> str:
    ext = ""
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
    suffix = f".{ext}" if ext else ""
    return f"{account_set_id}/invoices/{job_id}{suffix}"


def upload_bytes(*, key: str, content: bytes, content_type: str) -> str:
    """Store invoice bytes; returns the storage key."""
    if _use_memory():
        _MEMORY_STORE[key] = content
        return key

    import boto3

    bucket = os.environ["S3_BUCKET"]
    client = boto3.client("s3")
    client.put_object(Bucket=bucket, Key=key, Body=content, ContentType=content_type)
    return key


def download_bytes(key: str) -> bytes:
    """Retrieve stored invoice bytes."""
    if _use_memory():
        if key not in _MEMORY_STORE:
            raise FileNotFoundError(f"Object not found: {key}")
        return _MEMORY_STORE[key]

    import boto3

    bucket = os.environ["S3_BUCKET"]
    client = boto3.client("s3")
    response = client.get_object(Bucket=bucket, Key=key)
    body: Any = response["Body"]
    return body.read()


def clear_memory_store() -> None:
    """Test helper."""
    _MEMORY_STORE.clear()
