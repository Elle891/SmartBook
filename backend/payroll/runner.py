"""
Async helpers for Celery payroll tasks.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

T = TypeVar("T")


async def with_tenant_session(
    account_set_id: str,
    fn: Callable[[AsyncSession], Awaitable[T]],
) -> T:
    from platform.registry.service import get_tenant_db_config

    config = await get_tenant_db_config(account_set_id)
    engine = create_async_engine(config.async_url(), pool_pre_ping=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            result = await fn(session)
            await session.commit()
            return result
    finally:
        await engine.dispose()
