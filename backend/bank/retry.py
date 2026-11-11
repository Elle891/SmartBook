"""
Exponential backoff retry helper (Req 10.1).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0


def backoff_delays(max_retries: int = MAX_RETRIES, base_delay: float = BASE_DELAY_SECONDS) -> list[float]:
    """Return delay seconds for each retry attempt (exponential backoff)."""
    return [base_delay * (2**attempt) for attempt in range(max_retries)]


async def retry_with_backoff(
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY_SECONDS,
    operation_name: str = "bank_operation",
) -> T:
    """
    Execute *operation* with up to *max_retries* attempts and exponential backoff.
    """
    last_error: Exception | None = None
    delays = backoff_delays(max_retries, base_delay)

    for attempt in range(max_retries + 1):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            logger.warning(
                "%s failed (attempt %s/%s): %s",
                operation_name,
                attempt + 1,
                max_retries + 1,
                exc,
            )
            if attempt >= max_retries:
                break
            await asyncio.sleep(delays[attempt])

    assert last_error is not None
    raise last_error
