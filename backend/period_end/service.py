"""
Period-End Processor service.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ledger.calculations import compute_closing_balance, to_decimal
from models.account import Account
from models.account_set import AccountSet
from models.assets import FixedAsset
from models.ledger import AccountBalance
from models.voucher import Voucher
from period_end.accounts import (
    BALANCE_SHEET_TYPES,
    CARRY_ACCUMULATED_DEPRECIATION,
    CARRY_DEPRECIATION_EXPENSE,
    CARRY_PROFIT_LOSS,
    CARRY_RETAINED_EARNINGS,
    MissingRetainedEarningsAccountError,
    PeriodClosedError,
    PL_TYPES,
    UnapprovedVouchersError,
    get_carry_forward_account,
)
from period_end.periods import (
    assert_period_open,
    close_period_row,
    ensure_period_row,
    get_period,
    next_period_code,
)
from voucher.service import STATUS_APPROVED, STATUS_DELETED, create_voucher

logger = logging.getLogger(__name__)

VOUCHER_TYPE_TRANSFER = "Transfer"


async def _load_account_set(db: AsyncSession, account_set_id: str) -> AccountSet:
    result = await db.execute(
        select(AccountSet).where(AccountSet.id == account_set_id)
    )
    account_set = result.scalar_one_or_none()
    if account_set is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account set not found.")
    return account_set


async def _account_exists(db: AsyncSession, account_set_id: str, code: str) -> bool:
    result = await db.execute(
        select(Account.id).where(
            Account.account_set_id == account_set_id,
            Account.code == code,
        )
    )
    return result.scalar_one_or_none() is not None


async def _require_carry_accounts(
    db: AsyncSession,
    account_set_id: str,
    standard: str,
    carry_types: list[str],
) -> dict[str, str]:
    """Resolve and verify carry-forward accounts exist in the chart."""
    resolved: dict[str, str] = {}
    for ctype in carry_types:
        code = get_carry_forward_account(standard, ctype)
        if not await _account_exists(db, account_set_id, code):
            if ctype == CARRY_RETAINED_EARNINGS:
                raise MissingRetainedEarningsAccountError(
                    f"Retained earnings account '{code}' not found for standard {standard}."
                )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Required account '{code}' for {ctype} is missing from the chart of accounts.",
            )
        resolved[ctype] = code
    return resolved


async def _balances_with_types(
    db: AsyncSession,
    account_set_id: str,
    period_code: str,
    account_types: frozenset[str] | None = None,
) -> list[tuple[AccountBalance, Account]]:
    stmt = (
        select(AccountBalance, Account)
        .join(
            Account,
            (Account.account_set_id == AccountBalance.account_set_id)
            & (Account.code == AccountBalance.account_code),
        )
        .where(
            AccountBalance.account_set_id == account_set_id,
            AccountBalance.period_code == period_code,
        )
    )
    if account_types is not None:
        stmt = stmt.where(Account.account_type.in_(account_types))
    result = await db.execute(stmt)
    return list(result.all())


async def _count_unapproved_vouchers(
    db: AsyncSession,
    account_set_id: str,
    period_code: str,
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Voucher)
        .where(
            Voucher.account_set_id == account_set_id,
            Voucher.period_code == period_code,
            Voucher.status != STATUS_APPROVED,
            Voucher.status != STATUS_DELETED,
        )
    )
    return int(result.scalar_one() or 0)


def _closing_amount(balance: AccountBalance, account_type: str) -> Decimal:
    return to_decimal(balance.closing_balance)


async def _create_transfer_voucher(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    voucher_date: date,
    entries: list[dict[str, Any]],
    user_id: str,
    description: str,
) -> Any:
    """Create a balanced transfer voucher (draft)."""
    for i, entry in enumerate(entries):
        entry.setdefault("description", description)
        entry.setdefault("sequence", i)
    return await create_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_type=VOUCHER_TYPE_TRANSFER,
        voucher_date=voucher_date,
        entries=entries,
        attachments=[],
        created_by_user_id=user_id,
    )


async def carry_cost_forward(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    user_id: str,
    voucher_date: date | None = None,
) -> dict[str, Any]:
    """Transfer expense account balances to the profit/loss account (Req 15.1)."""
    await assert_period_open(db, account_set_id, period_code)
    account_set = await _load_account_set(db, account_set_id)
    accounts = await _require_carry_accounts(
        db,
        account_set_id,
        account_set.standard,
        [CARRY_PROFIT_LOSS],
    )
    pnl_code = accounts[CARRY_PROFIT_LOSS]

    rows = await _balances_with_types(
        db, account_set_id, period_code, frozenset({"Expense"})
    )
    entries: list[dict[str, Any]] = []
    total = Decimal("0")

    for balance, account in rows:
        amount = _closing_amount(balance, account.account_type)
        if amount <= 0:
            continue
        entries.append(
            {
                "account_code": account.code,
                "debit_amount": 0,
                "credit_amount": float(amount),
            }
        )
        total += amount

    if total == 0:
        return {
            "message": "No expense balances to carry forward.",
            "voucher_id": None,
            "total_amount": 0.0,
        }

    entries.append(
        {
            "account_code": pnl_code,
            "debit_amount": float(total),
            "credit_amount": 0,
        }
    )

    vdate = voucher_date or date.today()
    voucher = await _create_transfer_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_date=vdate,
        entries=entries,
        user_id=user_id,
        description=f"Cost carry-forward to {pnl_code}",
    )
    return {
        "message": "Cost carry-forward voucher created.",
        "voucher_id": str(voucher.id),
        "total_amount": float(total),
        "target_account": pnl_code,
    }


async def carry_profit_loss(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    user_id: str,
    voucher_date: date | None = None,
) -> dict[str, Any]:
    """Close P&L to retained earnings using the standard-designated account (Req 15.2, 15.3)."""
    await assert_period_open(db, account_set_id, period_code)
    account_set = await _load_account_set(db, account_set_id)
    accounts = await _require_carry_accounts(
        db,
        account_set_id,
        account_set.standard,
        [CARRY_PROFIT_LOSS, CARRY_RETAINED_EARNINGS],
    )
    pnl_code = accounts[CARRY_PROFIT_LOSS]
    retained_code = accounts[CARRY_RETAINED_EARNINGS]

    rows = await _balances_with_types(db, account_set_id, period_code, PL_TYPES)
    entries: list[dict[str, Any]] = []
    pnl_debit = Decimal("0")
    pnl_credit = Decimal("0")

    for balance, account in rows:
        amount = _closing_amount(balance, account.account_type)
        if amount == 0:
            continue
        if account.account_type == "Revenue":
            entries.append(
                {
                    "account_code": account.code,
                    "debit_amount": float(amount),
                    "credit_amount": 0,
                }
            )
            pnl_credit += amount
        else:
            entries.append(
                {
                    "account_code": account.code,
                    "debit_amount": 0,
                    "credit_amount": float(amount),
                }
            )
            pnl_debit += amount

    net_profit = pnl_credit - pnl_debit
    entries.extend(
        build_pnl_to_retained_entries(net_profit, pnl_code, retained_code)
    )

    if not entries:
        return {
            "message": "No P&L balances to carry forward.",
            "voucher_id": None,
            "net_profit": 0.0,
            "retained_earnings_account": retained_code,
        }

    vdate = voucher_date or date.today()
    voucher = await _create_transfer_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_date=vdate,
        entries=entries,
        user_id=user_id,
        description=f"P&L carry-forward to {retained_code}",
    )
    return {
        "message": "Profit/loss carry-forward voucher created.",
        "voucher_id": str(voucher.id),
        "net_profit": float(net_profit),
        "retained_earnings_account": retained_code,
    }


def build_pnl_to_retained_entries(
    net_profit: Decimal,
    pnl_code: str,
    retained_code: str,
) -> list[dict[str, Any]]:
    """Closing entries from P&L summary account to retained earnings (Property 3)."""
    entries: list[dict[str, Any]] = []
    if net_profit > 0:
        entries.append(
            {
                "account_code": pnl_code,
                "debit_amount": float(net_profit),
                "credit_amount": 0,
            }
        )
        entries.append(
            {
                "account_code": retained_code,
                "debit_amount": 0,
                "credit_amount": float(net_profit),
            }
        )
    elif net_profit < 0:
        loss = abs(net_profit)
        entries.append(
            {
                "account_code": pnl_code,
                "debit_amount": 0,
                "credit_amount": float(loss),
            }
        )
        entries.append(
            {
                "account_code": retained_code,
                "debit_amount": float(loss),
                "credit_amount": 0,
            }
        )
    return entries


async def calculate_depreciation(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    user_id: str,
    voucher_date: date | None = None,
) -> dict[str, Any]:
    """Calculate straight-line monthly depreciation and create voucher (Req 15.8)."""
    await assert_period_open(db, account_set_id, period_code)
    account_set = await _load_account_set(db, account_set_id)
    accounts = await _require_carry_accounts(
        db,
        account_set_id,
        account_set.standard,
        [CARRY_DEPRECIATION_EXPENSE, CARRY_ACCUMULATED_DEPRECIATION],
    )
    expense_code = accounts[CARRY_DEPRECIATION_EXPENSE]
    accum_code = accounts[CARRY_ACCUMULATED_DEPRECIATION]

    result = await db.execute(
        select(FixedAsset).where(
            FixedAsset.account_set_id == account_set_id,
            FixedAsset.is_disposed.is_(False),
            FixedAsset.useful_life_months > 0,
        )
    )
    assets = list(result.scalars().all())

    entries: list[dict[str, Any]] = []
    total_dep = Decimal("0")
    asset_details: list[dict[str, Any]] = []

    for asset in assets:
        monthly = to_decimal(asset.cost) / Decimal(asset.useful_life_months)
        monthly = monthly.quantize(Decimal("0.0001"))
        if monthly <= 0:
            continue
        total_dep += monthly
        asset_details.append(
            {
                "asset_id": str(asset.id),
                "name": asset.name,
                "depreciation_amount": float(monthly),
            }
        )
        asset.accumulated_depreciation = float(
            to_decimal(asset.accumulated_depreciation) + monthly
        )
        asset.net_book_value = float(
            max(to_decimal(asset.cost) - to_decimal(asset.accumulated_depreciation), Decimal("0"))
        )

    if total_dep == 0:
        return {
            "message": "No depreciation to record for active assets.",
            "voucher_id": None,
            "total_depreciation": 0.0,
            "assets": [],
        }

    entries.append(
        {
            "account_code": expense_code,
            "debit_amount": float(total_dep),
            "credit_amount": 0,
        }
    )
    entries.append(
        {
            "account_code": accum_code,
            "debit_amount": 0,
            "credit_amount": float(total_dep),
        }
    )

    vdate = voucher_date or date.today()
    voucher = await _create_transfer_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_date=vdate,
        entries=entries,
        user_id=user_id,
        description="Period depreciation",
    )
    await db.flush()
    return {
        "message": "Depreciation voucher created.",
        "voucher_id": str(voucher.id),
        "total_depreciation": float(total_dep),
        "assets": asset_details,
    }


async def get_next_period_opening_balances(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
) -> list[dict[str, Any]]:
    """Preview opening balances for the period following ``period_code``."""
    next_code = next_period_code(period_code)
    rows = await _balances_with_types(db, account_set_id, next_code, BALANCE_SHEET_TYPES)
    if rows:
        return [
            {
                "account_code": balance.account_code,
                "account_name": account.name,
                "account_type": account.account_type,
                "opening_balance": float(balance.opening_balance),
            }
            for balance, account in rows
        ]

    current = await _balances_with_types(
        db, account_set_id, period_code, BALANCE_SHEET_TYPES
    )
    return [
        {
            "account_code": balance.account_code,
            "account_name": account.name,
            "account_type": account.account_type,
            "opening_balance": float(balance.closing_balance),
        }
        for balance, account in current
        if to_decimal(balance.closing_balance) != 0
    ]


async def close_period(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    user_id: str,
) -> dict[str, Any]:
    """Close period after pre-flight; carry BS balances to next period (Req 15.4–15.7)."""
    unapproved = await _count_unapproved_vouchers(db, account_set_id, period_code)
    if unapproved > 0:
        raise UnapprovedVouchersError(unapproved)

    period = await ensure_period_row(db, account_set_id, period_code)
    if period.is_closed:
        raise PeriodClosedError(f"Period {period_code} is already closed.")

    next_code = next_period_code(period_code)
    await ensure_period_row(db, account_set_id, next_code)

    current_rows = await _balances_with_types(
        db, account_set_id, period_code, BALANCE_SHEET_TYPES
    )
    carried = 0

    for balance, account in current_rows:
        closing = to_decimal(balance.closing_balance)
        if closing == 0 and to_decimal(balance.opening_balance) == 0:
            continue

        result = await db.execute(
            select(AccountBalance).where(
                AccountBalance.account_set_id == account_set_id,
                AccountBalance.account_code == balance.account_code,
                AccountBalance.period_code == next_code,
            )
        )
        next_balance = result.scalar_one_or_none()
        if next_balance is None:
            next_balance = AccountBalance(
                account_set_id=account_set_id,
                account_code=balance.account_code,
                period_code=next_code,
                opening_balance=float(closing),
                total_debits=0,
                total_credits=0,
                closing_balance=float(closing),
            )
            db.add(next_balance)
        else:
            next_balance.opening_balance = float(closing)
            next_balance.total_debits = 0
            next_balance.total_credits = 0
            next_balance.closing_balance = float(
                compute_closing_balance(
                    closing,
                    Decimal("0"),
                    Decimal("0"),
                    account.account_type,
                )
            )
        carried += 1

    await close_period_row(db, period)
    logger.info(
        "Closed period %s for account_set %s — carried %s balance-sheet accounts to %s",
        period_code,
        account_set_id,
        carried,
        next_code,
    )

    return {
        "message": f"Period {period_code} closed successfully.",
        "period_code": period_code,
        "next_period_code": next_code,
        "accounts_carried": carried,
        "closed_at": period.closed_at.isoformat() if period.closed_at else None,
    }
