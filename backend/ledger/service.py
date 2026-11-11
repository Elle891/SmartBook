"""
Ledger Engine query service and export orchestration.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ledger.calculations import (
    group_subsidiary_entries,
    is_bank_account_code,
    is_cash_account_code,
)
from ledger.export import (
    ACCOUNT_SUMMARY_COLUMNS,
    GENERAL_LEDGER_COLUMNS,
    build_ledger_html,
    export_to_excel,
    export_to_pdf,
)
from models.account import Account
from models.ledger import AccountBalance, LedgerEntry
from models.voucher import Voucher, VoucherEntry

logger = logging.getLogger(__name__)


def _apply_date_filters(stmt, date_from: date | None, date_to: date | None):
    if date_from is not None:
        stmt = stmt.where(LedgerEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(LedgerEntry.entry_date <= date_to)
    return stmt


async def get_general_ledger(
    db: AsyncSession,
    *,
    account_set_id: str,
    account_code: str,
    period_code: str,
    date_from: date | None = None,
    date_to: date | None = None,
    dimension_value: str | None = None,
) -> dict[str, Any]:
    """General ledger with running balance (Req 14.1)."""
    stmt = (
        select(LedgerEntry)
        .where(
            LedgerEntry.account_set_id == account_set_id,
            LedgerEntry.account_code == account_code,
            LedgerEntry.period_code == period_code,
        )
        .order_by(LedgerEntry.entry_date, LedgerEntry.created_at)
    )
    stmt = _apply_date_filters(stmt, date_from, date_to)

    result = await db.execute(stmt)
    entries = list(result.scalars().all())

    if dimension_value is not None:
        filtered: list[LedgerEntry] = []
        for row in entries:
            ve = await db.get(VoucherEntry, row.entry_id)
            aux = (ve.aux_dimension_values or {}) if ve else {}
            if dimension_value in aux.values():
                filtered.append(row)
        entries = filtered

    return {
        "account_set_id": account_set_id,
        "account_code": account_code,
        "period_code": period_code,
        "entries": entries,
    }


async def get_subsidiary_ledger(
    db: AsyncSession,
    *,
    account_set_id: str,
    account_code: str,
    period_code: str,
    dimension: str,
    date_from: date | None = None,
    date_to: date | None = None,
    dimension_value: str | None = None,
) -> dict[str, Any]:
    """Subsidiary ledger grouped by auxiliary dimension (Req 14.2)."""
    stmt = (
        select(
            LedgerEntry,
            VoucherEntry.aux_dimension_values,
            Voucher.voucher_number,
            VoucherEntry.description,
        )
        .join(VoucherEntry, LedgerEntry.entry_id == VoucherEntry.id)
        .join(Voucher, LedgerEntry.voucher_id == Voucher.id)
        .where(
            LedgerEntry.account_set_id == account_set_id,
            LedgerEntry.account_code == account_code,
            LedgerEntry.period_code == period_code,
        )
        .order_by(LedgerEntry.entry_date, Voucher.voucher_number)
    )
    stmt = _apply_date_filters(stmt, date_from, date_to)
    result = await db.execute(stmt)

    rows: list[dict[str, Any]] = []
    for ledger, aux, voucher_number, description in result.all():
        aux_dict = aux or {}
        if dimension_value is not None and str(aux_dict.get(dimension)) != dimension_value:
            continue
        rows.append(
            {
                "id": str(ledger.id),
                "entry_date": ledger.entry_date,
                "voucher_number": voucher_number,
                "voucher_id": str(ledger.voucher_id),
                "account_code": ledger.account_code,
                "description": description,
                "debit_amount": float(ledger.debit_amount),
                "credit_amount": float(ledger.credit_amount),
                "running_balance": float(ledger.running_balance),
                "aux_dimension_values": aux_dict,
            }
        )

    groups = group_subsidiary_entries(rows, dimension)
    return {
        "account_set_id": account_set_id,
        "account_code": account_code,
        "period_code": period_code,
        "dimension": dimension,
        "groups": groups,
    }


async def _journal_for_account_prefix(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    code_matcher,
    date_from: date | None = None,
    date_to: date | None = None,
    account_code: str | None = None,
) -> list[dict[str, Any]]:
    stmt = (
        select(
            LedgerEntry,
            Voucher.voucher_number,
            Voucher.type,
            VoucherEntry.description,
            Account.name,
        )
        .join(Voucher, LedgerEntry.voucher_id == Voucher.id)
        .join(VoucherEntry, LedgerEntry.entry_id == VoucherEntry.id)
        .join(
            Account,
            (Account.account_set_id == LedgerEntry.account_set_id)
            & (Account.code == LedgerEntry.account_code),
        )
        .where(
            LedgerEntry.account_set_id == account_set_id,
            LedgerEntry.period_code == period_code,
        )
        .order_by(LedgerEntry.entry_date, Voucher.voucher_number)
    )
    if account_code:
        stmt = stmt.where(LedgerEntry.account_code == account_code)
    stmt = _apply_date_filters(stmt, date_from, date_to)
    result = await db.execute(stmt)

    journal: list[dict[str, Any]] = []
    for ledger, voucher_number, voucher_type, description, account_name in result.all():
        if not code_matcher(ledger.account_code):
            continue
        journal.append(
            {
                "entry_date": ledger.entry_date,
                "voucher_number": voucher_number,
                "voucher_type": voucher_type,
                "account_code": ledger.account_code,
                "account_name": account_name,
                "description": description,
                "debit_amount": float(ledger.debit_amount),
                "credit_amount": float(ledger.credit_amount),
                "running_balance": float(ledger.running_balance),
            }
        )
    return journal


async def get_cash_journal(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    date_from: date | None = None,
    date_to: date | None = None,
    account_code: str | None = None,
    dimension_value: str | None = None,
) -> dict[str, Any]:
    """Cash journal — account type 1010 / code 1001 (Req 14.3)."""
    entries = await _journal_for_account_prefix(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        code_matcher=is_cash_account_code,
        date_from=date_from,
        date_to=date_to,
        account_code=account_code,
    )
    if dimension_value:
        entries = [
            e
            for e in entries
            if dimension_value in (e.get("aux_dimension_values") or {}).values()
        ]
    return {
        "account_set_id": account_set_id,
        "period_code": period_code,
        "journal_type": "cash",
        "entries": entries,
    }


async def get_bank_journal(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    date_from: date | None = None,
    date_to: date | None = None,
    account_code: str | None = None,
    dimension_value: str | None = None,
) -> dict[str, Any]:
    """Bank journal — account type 1020 / code 1002 (Req 14.4)."""
    entries = await _journal_for_account_prefix(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        code_matcher=is_bank_account_code,
        date_from=date_from,
        date_to=date_to,
        account_code=account_code,
    )
    return {
        "account_set_id": account_set_id,
        "period_code": period_code,
        "journal_type": "bank",
        "entries": entries,
    }


async def get_account_summary(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    account_code: str | None = None,
) -> dict[str, Any]:
    """Account summary table (Req 14.5)."""
    stmt = (
        select(AccountBalance, Account.name)
        .join(
            Account,
            (Account.account_set_id == AccountBalance.account_set_id)
            & (Account.code == AccountBalance.account_code),
        )
        .where(
            AccountBalance.account_set_id == account_set_id,
            AccountBalance.period_code == period_code,
        )
        .order_by(AccountBalance.account_code)
    )
    if account_code:
        stmt = stmt.where(AccountBalance.account_code == account_code)

    result = await db.execute(stmt)
    rows = []
    for balance, name in result.all():
        rows.append(
            {
                "account_code": balance.account_code,
                "account_name": name,
                "opening_balance": float(balance.opening_balance),
                "total_debits": float(balance.total_debits),
                "total_credits": float(balance.total_credits),
                "closing_balance": float(balance.closing_balance),
            }
        )

    return {
        "account_set_id": account_set_id,
        "period_code": period_code,
        "rows": rows,
    }


async def export_ledger(
    db: AsyncSession,
    *,
    account_set_id: str,
    export_format: str,
    ledger_type: str,
    period_code: str,
    account_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    dimension: str | None = None,
) -> tuple[bytes, str, str]:
    """Export ledger data as PDF or Excel (Req 14.7). Returns (bytes, filename, content_type)."""
    fmt = export_format.lower()
    if fmt not in ("pdf", "excel", "xlsx"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="format must be 'pdf' or 'excel'",
        )

    rows: list[dict[str, Any]] = []
    title = f"Ledger — {ledger_type} — {period_code}"

    if ledger_type == "general":
        if not account_code:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="account_code is required for general ledger export",
            )
        data = await get_general_ledger(
            db,
            account_set_id=account_set_id,
            account_code=account_code,
            period_code=period_code,
            date_from=date_from,
            date_to=date_to,
        )
        for entry in data["entries"]:
            rows.append(
                {
                    "entry_date": entry.entry_date.isoformat(),
                    "voucher_number": "",
                    "account_code": entry.account_code,
                    "description": "",
                    "debit_amount": float(entry.debit_amount),
                    "credit_amount": float(entry.credit_amount),
                    "running_balance": float(entry.running_balance),
                }
            )
        columns = GENERAL_LEDGER_COLUMNS
    elif ledger_type == "account-summary":
        data = await get_account_summary(
            db, account_set_id=account_set_id, period_code=period_code, account_code=account_code
        )
        rows = data["rows"]
        columns = ACCOUNT_SUMMARY_COLUMNS
        title = f"Account Summary — {period_code}"
    elif ledger_type == "cash":
        data = await get_cash_journal(
            db,
            account_set_id=account_set_id,
            period_code=period_code,
            date_from=date_from,
            date_to=date_to,
            account_code=account_code,
        )
        rows = [
            {
                "entry_date": e["entry_date"].isoformat(),
                "voucher_number": e["voucher_number"],
                "account_code": e["account_code"],
                "description": e["description"],
                "debit_amount": e["debit_amount"],
                "credit_amount": e["credit_amount"],
                "running_balance": e["running_balance"],
            }
            for e in data["entries"]
        ]
        columns = GENERAL_LEDGER_COLUMNS
        title = f"Cash Journal — {period_code}"
    elif ledger_type == "bank":
        data = await get_bank_journal(
            db,
            account_set_id=account_set_id,
            period_code=period_code,
            date_from=date_from,
            date_to=date_to,
            account_code=account_code,
        )
        rows = [
            {
                "entry_date": e["entry_date"].isoformat(),
                "voucher_number": e["voucher_number"],
                "account_code": e["account_code"],
                "description": e["description"],
                "debit_amount": e["debit_amount"],
                "credit_amount": e["credit_amount"],
                "running_balance": e["running_balance"],
            }
            for e in data["entries"]
        ]
        columns = GENERAL_LEDGER_COLUMNS
        title = f"Bank Journal — {period_code}"
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported ledger_type: {ledger_type}",
        )

    if fmt == "pdf":
        html = build_ledger_html(title, rows, columns=columns)
        content = export_to_pdf(html)
        return content, f"ledger-{period_code}.pdf", "application/pdf"

    content = export_to_excel("Ledger", rows, columns)
    return (
        content,
        f"ledger-{period_code}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
