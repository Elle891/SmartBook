"""
Redis-backed session inactivity tracker.

Session key pattern: session:{session_id}
TTL: 15 minutes (900 seconds)

Redis URL is read from the REDIS_URL environment variable
(default: redis://localhost:6379/0).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_SESSION_TTL = 900  # 15 minutes in seconds
_KEY_PREFIX = "session:"


@lru_cache(maxsize=1)
def _get_redis() -> aioredis.Redis:
    """Return a cached async Redis client."""
    return aioredis.from_url(_REDIS_URL, decode_responses=True)


def _session_key(session_id: str) -> str:
    return f"{_KEY_PREFIX}{session_id}"


async def touch_session(user_id: str, session_id: str) -> None:
    """Reset the 15-minute inactivity TTL for the given session.

    Creates the session key if it does not exist yet.
    """
    redis = _get_redis()
    key = _session_key(session_id)
    await redis.set(key, user_id, ex=_SESSION_TTL)
    logger.debug("Session touched: %s (user=%s)", session_id, user_id)


async def invalidate_session(session_id: str) -> None:
    """Delete the session key, forcing immediate logout."""
    redis = _get_redis()
    await redis.delete(_session_key(session_id))
    logger.info("Session invalidated: %s", session_id)


async def is_session_valid(session_id: str) -> bool:
    """Return True if the session key exists in Redis (i.e. not expired)."""
    redis = _get_redis()
    result = await redis.exists(_session_key(session_id))
    return bool(result)
