"""
Redis Streams consumer for voucher-approved events.

Consumer group: ledger-engine
Stream key: voucher:approved (from voucher.service.VOUCHER_STREAM_KEY)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ledger.materializer import materialize_voucher
from platform.registry.service import get_tenant_db_config
from voucher.service import VOUCHER_STREAM_KEY

logger = logging.getLogger(__name__)

CONSUMER_GROUP = os.environ.get("LEDGER_CONSUMER_GROUP", "ledger-engine")
CONSUMER_NAME = os.environ.get("LEDGER_CONSUMER_NAME", "ledger-worker-1")
_BLOCK_MS = int(os.environ.get("LEDGER_CONSUMER_BLOCK_MS", "5000"))


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


async def _ensure_consumer_group(redis: aioredis.Redis) -> None:
    try:
        await redis.xgroup_create(
            VOUCHER_STREAM_KEY,
            CONSUMER_GROUP,
            id="0",
            mkstream=True,
        )
        logger.info("Created consumer group %s on %s", CONSUMER_GROUP, VOUCHER_STREAM_KEY)
    except Exception as exc:  # noqa: BLE001
        if "BUSYGROUP" not in str(exc):
            raise


async def _tenant_session(account_set_id: str) -> tuple[Any, AsyncSession]:
    """Create engine + session for a tenant (used by stream consumer)."""
    config = await get_tenant_db_config(account_set_id)
    engine = create_async_engine(
        config.async_url(),
        pool_pre_ping=True,
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    return engine, session


async def handle_voucher_approved_event(data: dict[str, str]) -> bool:
    """Process one stream message. Returns True on success."""
    voucher_id = data.get("voucher_id")
    account_set_id = data.get("account_set_id")
    if not voucher_id or not account_set_id:
        logger.warning("Skipping malformed voucher event: %s", data)
        return False

    engine = None
    try:
        engine, session = await _tenant_session(account_set_id)
        async with session:
            await materialize_voucher(session, voucher_id)
            await session.commit()
        return True
    except Exception:
        logger.exception(
            "Failed to materialize voucher %s for account_set %s",
            voucher_id,
            account_set_id,
        )
        return False
    finally:
        if engine is not None:
            await engine.dispose()


async def process_pending_voucher_events(
    batch_size: int = 10,
    *,
    block_ms: int = _BLOCK_MS,
) -> int:
    """Read and process pending voucher-approved events. Returns processed count."""
    redis = aioredis.from_url(_redis_url(), decode_responses=True)
    await _ensure_consumer_group(redis)

    processed = 0
    try:
        messages = await redis.xreadgroup(
            CONSUMER_GROUP,
            CONSUMER_NAME,
            {VOUCHER_STREAM_KEY: ">"},
            count=batch_size,
            block=block_ms,
        )
        if not messages:
            return 0

        for _stream, entries in messages:
            for msg_id, data in entries:
                ok = await handle_voucher_approved_event(data)
                if ok:
                    await redis.xack(VOUCHER_STREAM_KEY, CONSUMER_GROUP, msg_id)
                    processed += 1
                else:
                    logger.error("Event %s not acked due to processing failure", msg_id)
    finally:
        await redis.aclose()

    return processed


async def run_consumer_loop(poll_interval_ms: int = 5000) -> None:
    """Long-running consumer loop (for dedicated worker process)."""
    import asyncio

    logger.info("Starting ledger consumer loop group=%s", CONSUMER_GROUP)
    while True:
        count = await process_pending_voucher_events()
        if count == 0:
            await asyncio.sleep(poll_interval_ms / 1000)
