"""
Report Engine service — financial statements, export, persistence.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.account import Account
from models.account_set import AccountSet
from models.ledger import AccountBalance, LedgerEntry
from models.report_engine import GeneratedReport
from reports.builders import (
    build_account_summary_report,
    build_balance_sheet,
    build_cash_flow_statement,
    build_disclosure_notes,
    build_income_statement,
)
from reports.errors import MethodNotSupportedError, ReportTimeoutError, StandardMismatchError
from reports.export import export_report_csv, export_report_pdf
from reports.filters import ReportFilter
from reports.terminology import STANDARD_CAS, STANDARD_IFRS

logger = logging.getLogger(__name__)

MAX_TRANSACTIONS = 10_000
MAX_GENERATION_SECONDS = 10.0


async def _get_account_set(db: AsyncSession, account_set_id: str) -> AccountSet:
    result = await db.execute(select(AccountSet).where(AccountSet.id == account_set_id))
    account_set = result.scalar_one_or_none()
    if account_set is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account set not found.")
    return account_set


async def _load_balance_rows(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    account_code: str | None = None,
) -> list[dict[str, Any]]:
    stmt = (
        select(
            AccountBalance.account_code,
            Account.name,
            Account.account_type,
            AccountBalance.opening_balance,
            AccountBalance.total_debits,
            AccountBalance.total_credits,
            AccountBalance.closing_balance,
        )
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
    return [
        {
            "account_code": code,
            "account_name": name,
            "account_type": acct_type,
            "opening_balance": float(opening),
            "total_debits": float(debits),
            "total_credits": float(credits),
            "closing_balance": float(closing),
        }
        for code, name, acct_type, opening, debits, credits, closing in result.all()
    ]


async def _count_ledger_transactions(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(LedgerEntry)
        .where(
            LedgerEntry.account_set_id == account_set_id,
            LedgerEntry.period_code == period_code,
        )
    )
    return int(result.scalar_one())


async def _persist_report(
    db: AsyncSession,
    *,
    account_set_id: str,
    report_type: str,
    standard: str,
    filters: ReportFilter,
    data: dict[str, Any],
    user_id: str,
    generation_ms: int,
) -> GeneratedReport:
    report = GeneratedReport(
        account_set_id=account_set_id,
        report_type=report_type,
        standard=standard,
        filters={
            "period_code": filters.period_code,
            "date_from": filters.date_from.isoformat() if filters.date_from else None,
            "date_to": filters.date_to.isoformat() if filters.date_to else None,
            "report_currency": filters.report_currency,
            "entity_id": filters.entity_id,
            "entity_group_id": filters.entity_group_id,
        },
        data=data,
        generated_by=user_id,
        generation_ms=generation_ms,
    )
    db.add(report)
    await db.flush()
    data["report_id"] = str(report.id)
    return report


async def _generate_with_budget(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    user_id: str,
    report_type: str,
    standard: str,
    filters: ReportFilter,
    builder,
) -> dict[str, Any]:
    filters.validate()
    txn_count = await _count_ledger_transactions(
        db, account_set_id=account_set_id, period_code=period_code
    )
    if txn_count > MAX_TRANSACTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Period exceeds {MAX_TRANSACTIONS} transactions; narrow the date range.",
        )

    start = time.perf_counter()
    rows = await _load_balance_rows(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        account_code=filters.account_code,
    )
    account_set = await _get_account_set(db, account_set_id)
    currency = account_set.base_currency
    data = builder(
        standard=standard,
        rows=rows,
        currency=currency,
        report_currency=filters.report_currency,
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    if elapsed_ms > MAX_GENERATION_SECONDS * 1000:
        raise ReportTimeoutError(
            f"Report generation exceeded {MAX_GENERATION_SECONDS}s budget.",
            details={"generation_ms": elapsed_ms, "transaction_count": txn_count},
        )

    await _persist_report(
        db,
        account_set_id=account_set_id,
        report_type=report_type,
        standard=standard,
        filters=filters,
        data=data,
        user_id=user_id,
        generation_ms=elapsed_ms,
    )
    data["generation_ms"] = elapsed_ms
    data["transaction_count"] = txn_count
    return data


async def generate_balance_sheet(
    db: AsyncSession,
    *,
    account_set_id: str,
    filters: ReportFilter,
    user_id: str = "",
) -> dict[str, Any]:
    account_set = await _get_account_set(db, account_set_id)
    period_code = filters.effective_period_code()
    return await _generate_with_budget(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        user_id=user_id,
        report_type="BalanceSheet",
        standard=account_set.standard,
        filters=filters,
        builder=lambda **kw: build_balance_sheet(**kw),
    )


async def generate_income_statement(
    db: AsyncSession,
    *,
    account_set_id: str,
    filters: ReportFilter,
    user_id: str = "",
) -> dict[str, Any]:
    account_set = await _get_account_set(db, account_set_id)
    period_code = filters.effective_period_code()
    return await _generate_with_budget(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        user_id=user_id,
        report_type="IncomeStatement",
        standard=account_set.standard,
        filters=filters,
        builder=lambda **kw: build_income_statement(**kw),
    )


async def generate_cash_flow_statement(
    db: AsyncSession,
    *,
    account_set_id: str,
    filters: ReportFilter,
    user_id: str = "",
) -> dict[str, Any]:
    account_set = await _get_account_set(db, account_set_id)
    period_code = filters.effective_period_code()
    method = filters.cash_flow_method or "Indirect"

    if account_set.standard == STANDARD_CAS and method == "Direct":
        raise MethodNotSupportedError(
            "Direct cash flow method is only supported for IFRS account sets."
        )

    def _builder(**kw):
        return build_cash_flow_statement(**kw, method=method)

    return await _generate_with_budget(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        user_id=user_id,
        report_type="CashFlow",
        standard=account_set.standard,
        filters=filters,
        builder=_builder,
    )


async def generate_account_summary(
    db: AsyncSession,
    *,
    account_set_id: str,
    filters: ReportFilter,
    user_id: str = "",
) -> dict[str, Any]:
    account_set = await _get_account_set(db, account_set_id)
    period_code = filters.effective_period_code()
    return await _generate_with_budget(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        user_id=user_id,
        report_type="AccountSummary",
        standard=account_set.standard,
        filters=filters,
        builder=lambda **kw: build_account_summary_report(**kw),
    )


async def generate_disclosure_notes(
    db: AsyncSession,
    *,
    account_set_id: str,
    filters: ReportFilter,
    user_id: str = "",
) -> dict[str, Any]:
    account_set = await _get_account_set(db, account_set_id)
    if account_set.standard != STANDARD_IFRS:
        raise StandardMismatchError(
            "Disclosure notes are only available for IFRS account sets."
        )
    filters.validate()
    period_code = filters.effective_period_code()
    data = build_disclosure_notes(standard=STANDARD_IFRS, period_code=period_code)
    await _persist_report(
        db,
        account_set_id=account_set_id,
        report_type="DisclosureNotes",
        standard=STANDARD_IFRS,
        filters=filters,
        data=data,
        user_id=user_id,
        generation_ms=0,
    )
    return data


async def export_report(
    db: AsyncSession,
    *,
    account_set_id: str,
    report_id: str,
    export_format: str,
) -> tuple[bytes, str, str]:
    result = await db.execute(
        select(GeneratedReport).where(
            GeneratedReport.id == report_id,
            GeneratedReport.account_set_id == account_set_id,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    fmt = export_format.lower()
    if fmt == "csv":
        return (
            export_report_csv(report.data),
            "text/csv",
            f"{report.report_type}.csv",
        )
    if fmt == "pdf":
        return (
            export_report_pdf(report.data),
            "application/pdf",
            f"{report.report_type}.pdf",
        )
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="export_format must be pdf or csv.",
    )


async def get_report(
    db: AsyncSession,
    *,
    account_set_id: str,
    report_id: str,
) -> GeneratedReport:
    result = await db.execute(
        select(GeneratedReport).where(
            GeneratedReport.id == report_id,
            GeneratedReport.account_set_id == account_set_id,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return report
