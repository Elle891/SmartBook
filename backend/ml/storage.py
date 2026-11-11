"""Model artifact storage — S3 with in-memory fallback."""

from __future__ import annotations

import json
import os
import pickle
from typing import Any

_MEMORY_MODELS: dict[str, bytes] = {}
_MEMORY_META: dict[str, dict[str, Any]] = {}


def _use_memory() -> bool:
    return os.getenv("ML_STORAGE_BACKEND", "").lower() in ("memory", "test") or not os.getenv(
        "S3_BUCKET"
    )


def model_prefix(account_set_id: str) -> str:
    return f"models/{account_set_id}/current"


def model_key(account_set_id: str) -> str:
    return f"{model_prefix(account_set_id)}/model.pkl"


def metadata_key(account_set_id: str) -> str:
    return f"{model_prefix(account_set_id)}/metadata.json"


def snapshot_key(account_set_id: str, period_code: str) -> str:
    return f"models/{account_set_id}/forecast_snapshots/{period_code}.json"


def save_model_artifact(account_set_id: str, model: Any) -> str:
    key = model_key(account_set_id)
    payload = pickle.dumps(model)
    if _use_memory():
        _MEMORY_MODELS[key] = payload
        return key

    import boto3

    bucket = os.environ["S3_BUCKET"]
    client = boto3.client("s3")
    client.put_object(Bucket=bucket, Key=key, Body=payload, ContentType="application/octet-stream")
    return key


def load_model_artifact(account_set_id: str) -> Any:
    key = model_key(account_set_id)
    if _use_memory():
        if key not in _MEMORY_MODELS:
            raise FileNotFoundError(f"Model not found: {key}")
        return pickle.loads(_MEMORY_MODELS[key])

    import boto3

    bucket = os.environ["S3_BUCKET"]
    client = boto3.client("s3")
    response = client.get_object(Bucket=bucket, Key=key)
    return pickle.loads(response["Body"].read())


def save_metadata(account_set_id: str, metadata: dict[str, Any]) -> str:
    key = metadata_key(account_set_id)
    body = json.dumps(metadata).encode("utf-8")
    if _use_memory():
        _MEMORY_META[key] = metadata
        return key

    import boto3

    bucket = os.environ["S3_BUCKET"]
    client = boto3.client("s3")
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    return key


def load_metadata(account_set_id: str) -> dict[str, Any]:
    key = metadata_key(account_set_id)
    if _use_memory():
        if key not in _MEMORY_META:
            raise FileNotFoundError(f"Metadata not found: {key}")
        return dict(_MEMORY_META[key])

    import boto3

    bucket = os.environ["S3_BUCKET"]
    client = boto3.client("s3")
    response = client.get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


def save_snapshot_json(account_set_id: str, period_code: str, payload: dict[str, Any]) -> str:
    key = snapshot_key(account_set_id, period_code)
    body = json.dumps(payload).encode("utf-8")
    if _use_memory():
        _MEMORY_META[key] = payload
        return key

    import boto3

    bucket = os.environ["S3_BUCKET"]
    client = boto3.client("s3")
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    return key


def clear_memory_store() -> None:
    _MEMORY_MODELS.clear()
    _MEMORY_META.clear()
