"""
Period helpers — period codes, Period ORM rows, closed-period guards.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ledger import Period
from period_end.accounts import PeriodClosedError


def next_period_code(period_code: str) -> str:
    """Advance YYYYMM period code by one month."""
    year = int(period_code[:4])
    month = int(period_code[4:6])
    month += 1
    if month > 12:
        month = 1
        year += 1
    return f"{year}{month:02d}"


async def get_period(
    db: AsyncSession,
    account_set_id: str,
    period_code: str,
) -> Period | None:
    result = await db.execute(
        select(Period).where(
            Period.account_set_id == account_set_id,
            Period.period_code == period_code,
        )
    )
    return result.scalar_one_or_none()


async def ensure_period_row(
    db: AsyncSession,
    account_set_id: str,
    period_code: str,
) -> Period:
    period = await get_period(db, account_set_id, period_code)
    if period is not None:
        return period

    year = int(period_code[:4])
    month = int(period_code[4:6])
    period = Period(
        account_set_id=account_set_id,
        period_code=period_code,
        year=year,
        month=month,
        is_closed=False,
    )
    db.add(period)
    await db.flush()
    return period


async def assert_period_open(
    db: AsyncSession,
    account_set_id: str,
    period_code: str,
) -> Period:
    period = await get_period(db, account_set_id, period_code)
    if period is not None and period.is_closed:
        raise PeriodClosedError(
            f"Period {period_code} is closed and cannot accept new vouchers."
        )
    return period if period is not None else await ensure_period_row(
        db, account_set_id, period_code
    )


async def is_period_closed(
    db: AsyncSession,
    account_set_id: str,
    period_code: str,
) -> bool:
    period = await get_period(db, account_set_id, period_code)
    return period is not None and period.is_closed


async def close_period_row(db: AsyncSession, period: Period) -> None:
    period.is_closed = True
    period.closed_at = datetime.now(timezone.utc)
    await db.flush()
