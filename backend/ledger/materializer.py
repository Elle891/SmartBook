"""
Materialize LedgerEntry and AccountBalance rows when a voucher is approved.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ledger.calculations import (
    compute_closing_balance,
    compute_running_balance,
    net_change,
    to_decimal,
)
from models.account import Account
from models.ledger import AccountBalance, LedgerEntry
from models.voucher import Voucher, VoucherEntry

logger = logging.getLogger(__name__)


async def _get_account_types(
    db: AsyncSession, account_set_id: str, codes: set[str]
) -> dict[str, str]:
    if not codes:
        return {}
    result = await db.execute(
        select(Account.code, Account.account_type).where(
            Account.account_set_id == account_set_id,
            Account.code.in_(codes),
        )
    )
    return {row[0]: row[1] for row in result.all()}


async def _get_or_create_balance(
    db: AsyncSession,
    *,
    account_set_id: str,
    account_code: str,
    period_code: str,
) -> AccountBalance:
    result = await db.execute(
        select(AccountBalance).where(
            AccountBalance.account_set_id == account_set_id,
            AccountBalance.account_code == account_code,
            AccountBalance.period_code == period_code,
        )
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return row

    row = AccountBalance(
        account_set_id=account_set_id,
        account_code=account_code,
        period_code=period_code,
        opening_balance=0,
        total_debits=0,
        total_credits=0,
        closing_balance=0,
    )
    db.add(row)
    await db.flush()
    return row


async def _last_running_balance(
    db: AsyncSession,
    *,
    account_set_id: str,
    account_code: str,
    period_code: str,
) -> Decimal:
    result = await db.execute(
        select(LedgerEntry.running_balance)
        .where(
            LedgerEntry.account_set_id == account_set_id,
            LedgerEntry.account_code == account_code,
            LedgerEntry.period_code == period_code,
        )
        .order_by(LedgerEntry.entry_date.desc(), LedgerEntry.created_at.desc())
        .limit(1)
    )
    val = result.scalar_one_or_none()
    if val is None:
        balance = await _get_or_create_balance(
            db,
            account_set_id=account_set_id,
            account_code=account_code,
            period_code=period_code,
        )
        return to_decimal(balance.opening_balance)
    return to_decimal(val)


async def is_voucher_materialized(db: AsyncSession, voucher_id: str) -> bool:
    result = await db.execute(
        select(LedgerEntry.id)
        .where(LedgerEntry.voucher_id == voucher_id)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def materialize_voucher(db: AsyncSession, voucher_id: str) -> int:
    """Create ledger rows for an approved voucher. Returns number of lines created."""
    if await is_voucher_materialized(db, voucher_id):
        logger.info("Voucher %s already materialized — skipping", voucher_id)
        return 0

    result = await db.execute(select(Voucher).where(Voucher.id == voucher_id))
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise ValueError(f"Voucher not found: {voucher_id}")

    entries_result = await db.execute(
        select(VoucherEntry)
        .where(VoucherEntry.voucher_id == voucher.id)
        .order_by(VoucherEntry.sequence)
    )
    entries = list(entries_result.scalars().all())
    if not entries:
        return 0

    account_set_id = str(voucher.account_set_id)
    period_code = voucher.period_code
    entry_date = voucher.date

    codes = {e.account_code for e in entries}
    account_types = await _get_account_types(db, account_set_id, codes)

    created = 0
    for entry in entries:
        account_type = account_types.get(entry.account_code, "Asset")
        debit = to_decimal(entry.debit_amount)
        credit = to_decimal(entry.credit_amount)

        prev_running = await _last_running_balance(
            db,
            account_set_id=account_set_id,
            account_code=entry.account_code,
            period_code=period_code,
        )
        running = compute_running_balance(prev_running, account_type, debit, credit)

        ledger_row = LedgerEntry(
            account_set_id=account_set_id,
            account_code=entry.account_code,
            period_code=period_code,
            voucher_id=voucher.id,
            entry_id=entry.id,
            debit_amount=float(debit),
            credit_amount=float(credit),
            running_balance=float(running),
            entry_date=entry_date,
        )
        db.add(ledger_row)
        created += 1

        balance_row = await _get_or_create_balance(
            db,
            account_set_id=account_set_id,
            account_code=entry.account_code,
            period_code=period_code,
        )
        balance_row.total_debits = float(
            to_decimal(balance_row.total_debits) + debit
        )
        balance_row.total_credits = float(
            to_decimal(balance_row.total_credits) + credit
        )
        balance_row.closing_balance = float(
            compute_closing_balance(
                to_decimal(balance_row.opening_balance),
                to_decimal(balance_row.total_debits),
                to_decimal(balance_row.total_credits),
                account_type,
            )
        )

    await db.flush()
    logger.info(
        "Materialized voucher %s — %s ledger entries for account_set=%s period=%s",
        voucher_id,
        created,
        account_set_id,
        period_code,
    )
    return created
