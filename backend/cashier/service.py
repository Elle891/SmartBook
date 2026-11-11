"""
Cashier module service — orchestrates vouchers for cash/bank operations.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cashier.calculations import (
    build_reconciliation_report,
    compute_fx_balance,
    compute_functional_amount,
    to_decimal,
    validate_transfer_balanced,
)
from ledger.calculations import is_bank_account_code, is_cash_account_code
from models.account import Account
from models.account_set import AccountSet
from models.cashier import CashierAccount, CashierTransaction
from models.ledger import AccountBalance
from period_end.periods import assert_period_open
from voucher.service import create_voucher

logger = logging.getLogger(__name__)

CASHIER_TYPE_CASH = "Cash"
CASHIER_TYPE_BANK = "Bank"


def _validate_cashier_code(account_code: str, cashier_type: str) -> None:
    if cashier_type == CASHIER_TYPE_CASH and not is_cash_account_code(account_code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Account '{account_code}' is not a cash account (type 1010 / 1001).",
        )
    if cashier_type == CASHIER_TYPE_BANK and not is_bank_account_code(account_code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Account '{account_code}' is not a bank account (type 1020 / 1002).",
        )


async def _load_account_set(db: AsyncSession, account_set_id: str) -> AccountSet:
    result = await db.execute(
        select(AccountSet).where(AccountSet.id == account_set_id)
    )
    account_set = result.scalar_one_or_none()
    if account_set is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account set not found.")
    return account_set


async def _ensure_chart_account(
    db: AsyncSession,
    *,
    account_set_id: str,
    account_code: str,
    name: str,
    account_type: str,
    standard: str,
) -> Account:
    result = await db.execute(
        select(Account).where(
            Account.account_set_id == account_set_id,
            Account.code == account_code,
        )
    )
    account = result.scalar_one_or_none()
    if account is not None:
        return account

    account = Account(
        account_set_id=account_set_id,
        code=account_code,
        name=name,
        account_type=account_type,
        standard=standard,
        parent_code=None,
        level=1,
        is_leaf=True,
        is_active=True,
        aux_dimensions=[],
    )
    db.add(account)
    await db.flush()
    return account


async def _get_cashier_account(
    db: AsyncSession, account_set_id: str, account_code: str
) -> CashierAccount:
    result = await db.execute(
        select(CashierAccount).where(
            CashierAccount.account_set_id == account_set_id,
            CashierAccount.account_code == account_code,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cashier account '{account_code}' is not registered.",
        )
    return row


def _resolve_functional(
    amount: float,
    *,
    foreign_amount: float | None,
    exchange_rate: float | None,
    multi_currency_enabled: bool,
    base_currency: str,
    currency: str,
) -> tuple[Decimal, Decimal | None, Decimal | None, str | None]:
    amt = to_decimal(amount)
    f_amt = to_decimal(foreign_amount) if foreign_amount is not None else None
    rate = to_decimal(exchange_rate) if exchange_rate is not None else None
    foreign_ccy: str | None = None

    if multi_currency_enabled and currency != base_currency:
        if f_amt is None or rate is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="foreign_amount and exchange_rate are required for multi-currency transactions.",
            )
        foreign_ccy = currency
        functional = compute_functional_amount(
            amt, foreign_amount=f_amt, exchange_rate=rate
        )
        return functional, f_amt, rate, foreign_ccy

    functional = compute_functional_amount(amt)
    return functional, f_amt, rate, foreign_ccy


async def _persist_transaction(
    db: AsyncSession,
    *,
    account_set_id: str,
    voucher_id: str | None,
    transaction_type: str,
    primary_account_code: str,
    period_code: str,
    description: str,
    functional_amount: Decimal,
    counterparty_account_code: str | None = None,
    from_account_code: str | None = None,
    to_account_code: str | None = None,
    foreign_currency: str | None = None,
    foreign_amount: Decimal | None = None,
    exchange_rate: Decimal | None = None,
    income_amount: Decimal | None = None,
    expenditure_amount: Decimal | None = None,
) -> CashierTransaction:
    txn = CashierTransaction(
        account_set_id=account_set_id,
        voucher_id=voucher_id,
        transaction_type=transaction_type,
        primary_account_code=primary_account_code,
        counterparty_account_code=counterparty_account_code,
        from_account_code=from_account_code,
        to_account_code=to_account_code,
        period_code=period_code,
        description=description,
        foreign_currency=foreign_currency,
        foreign_amount=float(foreign_amount) if foreign_amount is not None else None,
        exchange_rate=float(exchange_rate) if exchange_rate is not None else None,
        functional_amount=float(functional_amount),
        income_amount=float(income_amount) if income_amount is not None else None,
        expenditure_amount=float(expenditure_amount) if expenditure_amount is not None else None,
    )
    db.add(txn)
    await db.flush()
    return txn


async def register_account(
    db: AsyncSession,
    *,
    account_set_id: str,
    account_code: str,
    cashier_type: str,
    name: str,
    currency: str,
    multi_currency_enabled: bool = False,
) -> CashierAccount:
    """Register a cash (1010) or bank (1020) account (Req 16.1)."""
    if cashier_type not in (CASHIER_TYPE_CASH, CASHIER_TYPE_BANK):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="cashier_type must be 'Cash' or 'Bank'.",
        )
    _validate_cashier_code(account_code, cashier_type)

    account_set = await _load_account_set(db, account_set_id)
    await _ensure_chart_account(
        db,
        account_set_id=account_set_id,
        account_code=account_code,
        name=name,
        account_type="Asset",
        standard=account_set.standard,
    )

    existing = await db.execute(
        select(CashierAccount).where(
            CashierAccount.account_set_id == account_set_id,
            CashierAccount.account_code == account_code,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cashier account '{account_code}' is already registered.",
        )

    if currency != account_set.base_currency:
        multi_currency_enabled = True

    row = CashierAccount(
        account_set_id=account_set_id,
        account_code=account_code,
        cashier_type=cashier_type,
        name=name,
        currency=currency,
        multi_currency_enabled=multi_currency_enabled,
    )
    db.add(row)
    await db.flush()
    return row


async def record_receipt(
    db: AsyncSession,
    *,
    account_set_id: str,
    account_code: str,
    counterparty_account_code: str,
    amount: float,
    period_code: str,
    description: str,
    user_id: str,
    transaction_date: date | None = None,
    foreign_amount: float | None = None,
    exchange_rate: float | None = None,
) -> dict[str, Any]:
    """Record cash receipt → Receipt voucher (Req 16.2)."""
    await assert_period_open(db, account_set_id, period_code)
    cashier_acct = await _get_cashier_account(db, account_set_id, account_code)
    account_set = await _load_account_set(db, account_set_id)

    functional, f_amt, rate, foreign_ccy = _resolve_functional(
        amount,
        foreign_amount=foreign_amount,
        exchange_rate=exchange_rate,
        multi_currency_enabled=cashier_acct.multi_currency_enabled,
        base_currency=account_set.base_currency,
        currency=cashier_acct.currency,
    )

    entries = [
        {
            "account_code": account_code,
            "debit_amount": float(functional),
            "credit_amount": 0,
            "description": description,
        },
        {
            "account_code": counterparty_account_code,
            "debit_amount": 0,
            "credit_amount": float(functional),
            "description": description,
        },
    ]

    vdate = transaction_date or date.today()
    voucher = await create_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_type="Receipt",
        voucher_date=vdate,
        entries=entries,
        attachments=[],
        created_by_user_id=user_id,
    )

    txn = await _persist_transaction(
        db,
        account_set_id=account_set_id,
        voucher_id=str(voucher.id),
        transaction_type="receipt",
        primary_account_code=account_code,
        counterparty_account_code=counterparty_account_code,
        period_code=period_code,
        description=description,
        functional_amount=functional,
        foreign_currency=foreign_ccy,
        foreign_amount=f_amt,
        exchange_rate=rate,
    )

    return {
        "message": "Receipt recorded.",
        "voucher_id": str(voucher.id),
        "transaction_id": str(txn.id),
        "functional_amount": float(functional),
    }


async def record_payment(
    db: AsyncSession,
    *,
    account_set_id: str,
    account_code: str,
    counterparty_account_code: str,
    amount: float,
    period_code: str,
    description: str,
    user_id: str,
    transaction_date: date | None = None,
    foreign_amount: float | None = None,
    exchange_rate: float | None = None,
) -> dict[str, Any]:
    """Record cash payment → Payment voucher (Req 16.3)."""
    await assert_period_open(db, account_set_id, period_code)
    cashier_acct = await _get_cashier_account(db, account_set_id, account_code)
    account_set = await _load_account_set(db, account_set_id)

    functional, f_amt, rate, foreign_ccy = _resolve_functional(
        amount,
        foreign_amount=foreign_amount,
        exchange_rate=exchange_rate,
        multi_currency_enabled=cashier_acct.multi_currency_enabled,
        base_currency=account_set.base_currency,
        currency=cashier_acct.currency,
    )

    entries = [
        {
            "account_code": counterparty_account_code,
            "debit_amount": float(functional),
            "credit_amount": 0,
            "description": description,
        },
        {
            "account_code": account_code,
            "debit_amount": 0,
            "credit_amount": float(functional),
            "description": description,
        },
    ]

    vdate = transaction_date or date.today()
    voucher = await create_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_type="Payment",
        voucher_date=vdate,
        entries=entries,
        attachments=[],
        created_by_user_id=user_id,
    )

    txn = await _persist_transaction(
        db,
        account_set_id=account_set_id,
        voucher_id=str(voucher.id),
        transaction_type="payment",
        primary_account_code=account_code,
        counterparty_account_code=counterparty_account_code,
        period_code=period_code,
        description=description,
        functional_amount=functional,
        foreign_currency=foreign_ccy,
        foreign_amount=f_amt,
        exchange_rate=rate,
    )

    return {
        "message": "Payment recorded.",
        "voucher_id": str(voucher.id),
        "transaction_id": str(txn.id),
        "functional_amount": float(functional),
    }


async def record_transfer(
    db: AsyncSession,
    *,
    account_set_id: str,
    from_account_code: str,
    to_account_code: str,
    income_amount: float,
    expenditure_amount: float,
    period_code: str,
    description: str,
    user_id: str,
    transaction_date: date | None = None,
    income_foreign_amount: float | None = None,
    income_exchange_rate: float | None = None,
    expenditure_foreign_amount: float | None = None,
    expenditure_exchange_rate: float | None = None,
) -> dict[str, Any]:
    """Fund transfer between registered accounts; income must equal expenditure (Req 16.4, 16.5)."""
    await assert_period_open(db, account_set_id, period_code)

    income = to_decimal(income_amount)
    expenditure = to_decimal(expenditure_amount)
    try:
        validate_transfer_balanced(income, expenditure)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await _get_cashier_account(db, account_set_id, from_account_code)
    await _get_cashier_account(db, account_set_id, to_account_code)

    entries = [
        {
            "account_code": from_account_code,
            "debit_amount": 0,
            "credit_amount": float(expenditure),
            "description": description,
        },
        {
            "account_code": to_account_code,
            "debit_amount": float(income),
            "credit_amount": 0,
            "description": description,
        },
    ]

    vdate = transaction_date or date.today()
    voucher = await create_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_type="Transfer",
        voucher_date=vdate,
        entries=entries,
        attachments=[],
        created_by_user_id=user_id,
    )

    txn = await _persist_transaction(
        db,
        account_set_id=account_set_id,
        voucher_id=str(voucher.id),
        transaction_type="transfer",
        primary_account_code=to_account_code,
        from_account_code=from_account_code,
        to_account_code=to_account_code,
        period_code=period_code,
        description=description,
        functional_amount=income,
        income_amount=income,
        expenditure_amount=expenditure,
        foreign_amount=to_decimal(income_foreign_amount) if income_foreign_amount else None,
        exchange_rate=to_decimal(income_exchange_rate) if income_exchange_rate else None,
        foreign_currency=None,
    )

    return {
        "message": "Transfer recorded.",
        "voucher_id": str(voucher.id),
        "transaction_id": str(txn.id),
        "income_amount": float(income),
        "expenditure_amount": float(expenditure),
    }


async def reconcile_physical_cash(
    db: AsyncSession,
    *,
    account_set_id: str,
    account_code: str,
    period_code: str,
    physical_count: float,
) -> dict[str, Any]:
    """Compare system cash balance vs physical count (Req 16.8)."""
    await _get_cashier_account(db, account_set_id, account_code)
    if not is_cash_account_code(account_code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Physical cash reconciliation applies to cash accounts only.",
        )

    result = await db.execute(
        select(AccountBalance).where(
            AccountBalance.account_set_id == account_set_id,
            AccountBalance.account_code == account_code,
            AccountBalance.period_code == period_code,
        )
    )
    balance = result.scalar_one_or_none()
    system = to_decimal(balance.closing_balance) if balance else Decimal("0")

    return build_reconciliation_report(
        account_code=account_code,
        system_balance=system,
        physical_count=to_decimal(physical_count),
    )


async def get_fx_balance(
    db: AsyncSession,
    *,
    account_set_id: str,
    account_code: str,
    period_code: str | None = None,
) -> dict[str, Any]:
    """Functional currency balance for a foreign-currency cashier account (Req 16.7)."""
    cashier_acct = await _get_cashier_account(db, account_set_id, account_code)
    account_set = await _load_account_set(db, account_set_id)

    stmt = select(CashierTransaction).where(
        CashierTransaction.account_set_id == account_set_id,
        CashierTransaction.primary_account_code == account_code,
    )
    if period_code:
        stmt = stmt.where(CashierTransaction.period_code == period_code)

    result = await db.execute(stmt)
    txns = [
        {
            "primary_account_code": t.primary_account_code,
            "foreign_currency": t.foreign_currency,
            "foreign_amount": t.foreign_amount,
            "functional_amount": t.functional_amount,
        }
        for t in result.scalars().all()
    ]

    report = compute_fx_balance(
        txns,
        account_code=account_code,
        base_currency=account_set.base_currency,
    )
    report["currency"] = cashier_acct.currency
    report["multi_currency_enabled"] = cashier_acct.multi_currency_enabled
    report["period_code"] = period_code
    return report
