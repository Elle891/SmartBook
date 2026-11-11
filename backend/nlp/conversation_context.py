"""Redis-backed conversation context with in-memory fallback."""

from __future__ import annotations

import json
import os
from typing import Any

MAX_TURNS = 10
_KEY_PREFIX = "nlp:session:"

_MEMORY: dict[str, list[dict[str, str]]] = {}


def _session_key(session_id: str) -> str:
    return f"{_KEY_PREFIX}{session_id}"


def _use_memory() -> bool:
    return os.getenv("NLP_CONTEXT_BACKEND", "").lower() in ("memory", "test") or not os.getenv(
        "REDIS_URL"
    )


async def get_context(session_id: str) -> list[dict[str, str]]:
    if _use_memory():
        return list(_MEMORY.get(session_id, []))

    import redis.asyncio as aioredis

    client = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        raw = await client.get(_session_key(session_id))
        if not raw:
            return []
        turns: list[dict[str, str]] = json.loads(raw)
        return turns[-MAX_TURNS:]
    finally:
        await client.aclose()


async def append_turn(session_id: str, *, role: str, content: str, intent: str | None = None) -> None:
    turns = await get_context(session_id)
    turn: dict[str, str] = {"role": role, "content": content}
    if intent:
        turn["intent"] = intent
    turns.append(turn)
    turns = turns[-MAX_TURNS:]

    if _use_memory():
        _MEMORY[session_id] = turns
        return

    import redis.asyncio as aioredis

    client = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        await client.set(_session_key(session_id), json.dumps(turns), ex=86400)
    finally:
        await client.aclose()


async def clear_context(session_id: str) -> None:
    if _use_memory():
        _MEMORY.pop(session_id, None)
        return

    import redis.asyncio as aioredis

    client = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        await client.delete(_session_key(session_id))
    finally:
        await client.aclose()


def clear_memory_store() -> None:
    _MEMORY.clear()
