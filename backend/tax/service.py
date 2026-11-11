"""
Tax Module service — filing reports, adjustments, submission, history.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.account import Account
from models.ledger import AccountBalance
from models.reports import TaxFiling
from tax import aggregation, clients

logger = logging.getLogger(__name__)

STATUS_DRAFT = "Draft"
STATUS_SUBMITTED = "Submitted"
STATUS_FAILED = "Failed"


async def _load_balance_rows(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
) -> list[dict[str, Any]]:
    stmt = (
        select(
            AccountBalance.account_code,
            Account.name,
            Account.account_type,
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
    )
    result = await db.execute(stmt)
    return [
        {
            "account_code": code,
            "account_name": name,
            "account_type": acct_type,
            "total_debits": float(debits),
            "total_credits": float(credits),
            "closing_balance": float(closing),
        }
        for code, name, acct_type, debits, credits, closing in result.all()
    ]


async def generate_filing_report(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    tax_type: str,
) -> TaxFiling:
    """Generate VAT or CIT filing report from ledger (Req 21.1, 21.2)."""
    tax_type = tax_type.upper()
    if tax_type not in (aggregation.TAX_TYPE_VAT, aggregation.TAX_TYPE_CIT):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tax_type must be VAT or CIT.",
        )

    rows = await _load_balance_rows(db, account_set_id=account_set_id, period_code=period_code)
    if tax_type == aggregation.TAX_TYPE_VAT:
        report_data = aggregation.build_vat_report(rows, period_code=period_code)
    else:
        report_data = aggregation.build_cit_report(rows, period_code=period_code)

    existing = await db.execute(
        select(TaxFiling).where(
            TaxFiling.account_set_id == account_set_id,
            TaxFiling.period_code == period_code,
            TaxFiling.tax_type == tax_type,
            TaxFiling.status == STATUS_DRAFT,
        )
    )
    filing = existing.scalar_one_or_none()
    if filing is None:
        filing = TaxFiling(
            account_set_id=account_set_id,
            period_code=period_code,
            tax_type=tax_type,
            status=STATUS_DRAFT,
            report_data=report_data,
        )
        db.add(filing)
    else:
        filing.report_data = report_data
    await db.flush()
    return filing


async def adjust_line_item(
    db: AsyncSession,
    *,
    account_set_id: str,
    filing_id: str,
    line_id: str,
    value: float,
) -> TaxFiling:
    """Review and adjust line item before submission (Req 21.3)."""
    filing = await _get_filing(db, account_set_id, filing_id)
    if filing.status != STATUS_DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft filings can be adjusted.",
        )
    try:
        filing.report_data = aggregation.apply_line_adjustment(
            filing.report_data, line_id, value
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    await db.flush()
    return filing


async def submit_filing(
    db: AsyncSession,
    *,
    account_set_id: str,
    filing_id: str,
) -> dict[str, Any]:
    """Submit filing to tax authority (Req 21.4–21.6)."""
    filing = await _get_filing(db, account_set_id, filing_id)
    if filing.status == STATUS_SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Filing already submitted.",
        )

    result = await clients.submit_to_tax_authority(
        account_set_id=account_set_id,
        filing_id=str(filing.id),
        tax_type=filing.tax_type,
        period_code=filing.period_code,
        report_data=filing.report_data,
    )

    if result["success"]:
        filing.status = STATUS_SUBMITTED
        filing.confirmation_number = result["confirmation_number"]
        filing.submitted_at = datetime.now(timezone.utc)
        report_data = dict(filing.report_data)
        report_data.pop("last_submission_error", None)
        filing.report_data = report_data
    else:
        filing.status = STATUS_FAILED
        report_data = dict(filing.report_data)
        report_data["last_submission_error"] = result["message"]
        filing.report_data = report_data

    await db.flush()
    return {
        "filing_id": str(filing.id),
        "success": result["success"],
        "status": filing.status,
        "confirmation_number": filing.confirmation_number,
        "submitted_at": filing.submitted_at.isoformat() if filing.submitted_at else None,
        "message": result["message"],
        "report_data_preserved": True,
    }


async def get_filing_history(
    db: AsyncSession,
    *,
    account_set_id: str,
    tax_type: str | None = None,
) -> list[dict[str, Any]]:
    """History of submitted filings (Req 21.7)."""
    stmt = (
        select(TaxFiling)
        .where(
            TaxFiling.account_set_id == account_set_id,
            TaxFiling.status == STATUS_SUBMITTED,
        )
        .order_by(TaxFiling.submitted_at.desc())
    )
    if tax_type:
        stmt = stmt.where(TaxFiling.tax_type == tax_type.upper())

    result = await db.execute(stmt)
    filings = list(result.scalars().all())
    return [
        {
            "id": str(f.id),
            "period_code": f.period_code,
            "tax_type": f.tax_type,
            "status": f.status,
            "confirmation_number": f.confirmation_number,
            "submitted_at": f.submitted_at.isoformat() if f.submitted_at else None,
            "created_at": f.created_at.isoformat(),
        }
        for f in filings
    ]


async def get_filing(
    db: AsyncSession,
    *,
    account_set_id: str,
    filing_id: str,
) -> TaxFiling:
    return await _get_filing(db, account_set_id, filing_id)


async def _get_filing(
    db: AsyncSession,
    account_set_id: str,
    filing_id: str,
) -> TaxFiling:
    result = await db.execute(
        select(TaxFiling).where(
            TaxFiling.id == filing_id,
            TaxFiling.account_set_id == account_set_id,
        )
    )
    filing = result.scalar_one_or_none()
    if filing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax filing not found.")
    return filing
