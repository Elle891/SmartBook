"""
Redis balance cache (Req 4.6 — 1 hour TTL).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

BALANCE_CACHE_TTL_SECONDS = 3600


def _redis() -> aioredis.Redis:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return aioredis.from_url(url, decode_responses=True)


def balance_cache_key(connection_id: str, as_of: str | None = None) -> str:
    suffix = as_of or "current"
    return f"bank:balance:{connection_id}:{suffix}"


async def get_cached_balance(connection_id: str, as_of: str | None = None) -> dict[str, Any] | None:
    redis = _redis()
    try:
        raw = await redis.get(balance_cache_key(connection_id, as_of))
        if not raw:
            return None
        return json.loads(raw)
    finally:
        await redis.aclose()


async def set_cached_balance(
    connection_id: str,
    payload: dict[str, Any],
    *,
    as_of: str | None = None,
    ttl_seconds: int = BALANCE_CACHE_TTL_SECONDS,
) -> None:
    redis = _redis()
    try:
        data = {
            **payload,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        await redis.setex(
            balance_cache_key(connection_id, as_of),
            ttl_seconds,
            json.dumps(data),
        )
    finally:
        await redis.aclose()
