"""
Reconciliation Engine service.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.bank import BankConnection, BankTransaction, ReconciliationMatch, ReconciliationSession
from models.voucher import Voucher, VoucherEntry
from reconciliation.matching import (
    BankCandidate,
    InternalCandidate,
    auto_match_candidates,
    compute_difference,
    signed_voucher_amount,
)
from voucher.service import write_tenant_audit

BANK_ACCOUNT_PREFIX = "1020"
VOUCHER_APPROVED = "Approved"


def _period_bounds(period_code: str) -> tuple[date, date]:
    year = int(period_code[:4])
    month = int(period_code[4:6])
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


async def _get_session(
    db: AsyncSession,
    *,
    account_set_id: str,
    session_id: str,
) -> ReconciliationSession:
    result = await db.execute(
        select(ReconciliationSession).where(
            ReconciliationSession.id == session_id,
            ReconciliationSession.account_set_id == account_set_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation session not found.")
    return session


async def _load_bank_candidates(
    db: AsyncSession,
    *,
    account_set_id: str,
    connection_id: str,
    period_code: str,
    session_id: str,
) -> list[BankCandidate]:
    start, end = _period_bounds(period_code)
    matched_ids = await db.execute(
        select(ReconciliationMatch.bank_transaction_id).where(
            ReconciliationMatch.session_id == session_id
        )
    )
    excluded = {str(row[0]) for row in matched_ids if row[0]}

    result = await db.execute(
        select(BankTransaction).where(
            BankTransaction.account_set_id == account_set_id,
            BankTransaction.connection_id == connection_id,
            BankTransaction.date >= start,
            BankTransaction.date <= end,
            BankTransaction.is_reconciled.is_(False),
        )
    )
    rows: list[BankCandidate] = []
    for txn in result.scalars():
        if str(txn.id) in excluded:
            continue
        rows.append(
            BankCandidate(
                transaction_id=str(txn.id),
                date=txn.date,
                amount=float(txn.amount),
                direction=txn.direction,
                description=txn.description,
            )
        )
    return rows


async def _load_internal_candidates(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    session_id: str,
) -> list[InternalCandidate]:
    matched_ids = await db.execute(
        select(ReconciliationMatch.voucher_entry_id).where(
            ReconciliationMatch.session_id == session_id,
            ReconciliationMatch.voucher_entry_id.is_not(None),
        )
    )
    excluded = {str(row[0]) for row in matched_ids if row[0]}

    result = await db.execute(
        select(VoucherEntry, Voucher)
        .join(Voucher, VoucherEntry.voucher_id == Voucher.id)
        .where(
            Voucher.account_set_id == account_set_id,
            Voucher.period_code == period_code,
            Voucher.status == VOUCHER_APPROVED,
            VoucherEntry.account_code.like(f"{BANK_ACCOUNT_PREFIX}%"),
        )
    )

    rows: list[InternalCandidate] = []
    for entry, voucher in result.all():
        if str(entry.id) in excluded:
            continue
        amount = signed_voucher_amount(float(entry.debit_amount), float(entry.credit_amount))
        if amount == 0:
            continue
        rows.append(
            InternalCandidate(
                entry_id=str(entry.id),
                date=voucher.date,
                amount=amount,
                description=entry.description or "",
            )
        )
    return rows


async def _apply_matches(
    db: AsyncSession,
    *,
    session_id: str,
    proposals: list,
) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    for proposal in proposals:
        bank_result = await db.execute(
            select(BankTransaction).where(BankTransaction.id == proposal.bank_transaction_id)
        )
        bank_txn = bank_result.scalar_one_or_none()
        if bank_txn is None:
            continue

        match = ReconciliationMatch(
            session_id=uuid.UUID(session_id),
            bank_transaction_id=uuid.UUID(proposal.bank_transaction_id),
            voucher_entry_id=uuid.UUID(proposal.voucher_entry_id),
            match_type=proposal.match_type,
        )
        db.add(match)
        bank_txn.is_reconciled = True
        created.append(
            {
                "match_id": str(match.id),
                "bank_transaction_id": proposal.bank_transaction_id,
                "voucher_entry_id": proposal.voucher_entry_id,
                "match_type": proposal.match_type,
            }
        )
    await db.flush()
    return created


async def initiate_reconciliation(
    db: AsyncSession,
    *,
    account_set_id: str,
    connection_id: str,
    period_code: str,
    user_id: str,
) -> dict[str, Any]:
    """Start a reconciliation session (Req 5.1)."""
    conn_result = await db.execute(
        select(BankConnection).where(
            BankConnection.id == connection_id,
            BankConnection.account_set_id == account_set_id,
        )
    )
    if conn_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank connection not found.")

    session = ReconciliationSession(
        account_set_id=uuid.UUID(account_set_id),
        connection_id=uuid.UUID(connection_id),
        period_code=period_code,
        status="InProgress",
    )
    db.add(session)
    await db.flush()

    await write_tenant_audit(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        action="reconciliation.initiate",
        entity_type="ReconciliationSession",
        entity_id=str(session.id),
        new_value={"connection_id": connection_id, "period_code": period_code},
    )

    return {
        "session_id": str(session.id),
        "connection_id": connection_id,
        "period_code": period_code,
        "status": session.status,
    }


async def auto_match(
    db: AsyncSession,
    *,
    account_set_id: str,
    session_id: str,
    fuzzy_threshold: int = 3,
) -> dict[str, Any]:
    """Run exact then fuzzy matching (Req 5.2–5.4)."""
    session = await _get_session(db, account_set_id=account_set_id, session_id=session_id)
    bank_rows = await _load_bank_candidates(
        db,
        account_set_id=account_set_id,
        connection_id=str(session.connection_id),
        period_code=session.period_code,
        session_id=session_id,
    )
    internal_rows = await _load_internal_candidates(
        db,
        account_set_id=account_set_id,
        period_code=session.period_code,
        session_id=session_id,
    )

    proposals = auto_match_candidates(
        bank_rows, internal_rows, fuzzy_threshold=fuzzy_threshold
    )
    matches = await _apply_matches(db, session_id=session_id, proposals=proposals)

    return {
        "session_id": session_id,
        "matched_count": len(matches),
        "matches": matches,
    }


async def manual_match(
    db: AsyncSession,
    *,
    account_set_id: str,
    session_id: str,
    bank_transaction_id: str,
    voucher_entry_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Manually link bank and internal entries (Req 5.7–5.8)."""
    session = await _get_session(db, account_set_id=account_set_id, session_id=session_id)

    bank_result = await db.execute(
        select(BankTransaction).where(
            BankTransaction.id == bank_transaction_id,
            BankTransaction.account_set_id == account_set_id,
            BankTransaction.connection_id == session.connection_id,
        )
    )
    bank_txn = bank_result.scalar_one_or_none()
    if bank_txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank transaction not found.")

    entry_result = await db.execute(
        select(VoucherEntry, Voucher)
        .join(Voucher, VoucherEntry.voucher_id == Voucher.id)
        .where(
            VoucherEntry.id == voucher_entry_id,
            Voucher.account_set_id == account_set_id,
            Voucher.period_code == session.period_code,
        )
    )
    row = entry_result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voucher entry not found.")

    match = ReconciliationMatch(
        session_id=uuid.UUID(session_id),
        bank_transaction_id=uuid.UUID(bank_transaction_id),
        voucher_entry_id=uuid.UUID(voucher_entry_id),
        match_type="Manual",
    )
    db.add(match)
    bank_txn.is_reconciled = True
    await db.flush()

    await write_tenant_audit(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        action="reconciliation.manual_match",
        entity_type="ReconciliationMatch",
        entity_id=str(match.id),
        new_value={
            "bank_transaction_id": bank_transaction_id,
            "voucher_entry_id": voucher_entry_id,
        },
    )

    return {
        "match_id": str(match.id),
        "session_id": session_id,
        "bank_transaction_id": bank_transaction_id,
        "voucher_entry_id": voucher_entry_id,
        "match_type": "Manual",
        "reconciled": True,
    }


async def get_reconciliation_report(
    db: AsyncSession,
    *,
    account_set_id: str,
    session_id: str,
) -> dict[str, Any]:
    """Return matched, unmatched, and missing items (Req 5.6)."""
    session = await _get_session(db, account_set_id=account_set_id, session_id=session_id)

    match_result = await db.execute(
        select(ReconciliationMatch).where(ReconciliationMatch.session_id == session_id)
    )
    matches = list(match_result.scalars())

    matched: list[dict[str, Any]] = []
    matched_bank_ids: set[str] = set()
    matched_entry_ids: set[str] = set()
    for m in matches:
        matched.append(
            {
                "match_id": str(m.id),
                "bank_transaction_id": str(m.bank_transaction_id),
                "voucher_entry_id": str(m.voucher_entry_id) if m.voucher_entry_id else None,
                "match_type": m.match_type,
            }
        )
        matched_bank_ids.add(str(m.bank_transaction_id))
        if m.voucher_entry_id:
            matched_entry_ids.add(str(m.voucher_entry_id))

    start, end = _period_bounds(session.period_code)
    bank_result = await db.execute(
        select(BankTransaction).where(
            BankTransaction.account_set_id == account_set_id,
            BankTransaction.connection_id == session.connection_id,
            BankTransaction.date >= start,
            BankTransaction.date <= end,
        )
    )
    all_bank = list(bank_result.scalars())

    internal_rows = await _load_internal_candidates(
        db,
        account_set_id=account_set_id,
        period_code=session.period_code,
        session_id=session_id,
    )
    # Include all internal candidates for report, not just unmatched from loader
    internal_result = await db.execute(
        select(VoucherEntry, Voucher)
        .join(Voucher, VoucherEntry.voucher_id == Voucher.id)
        .where(
            Voucher.account_set_id == account_set_id,
            Voucher.period_code == session.period_code,
            Voucher.status == VOUCHER_APPROVED,
            VoucherEntry.account_code.like(f"{BANK_ACCOUNT_PREFIX}%"),
        )
    )
    all_internal: list[dict[str, Any]] = []
    for entry, voucher in internal_result.all():
        amount = signed_voucher_amount(float(entry.debit_amount), float(entry.credit_amount))
        if amount == 0:
            continue
        all_internal.append(
            {
                "entry_id": str(entry.id),
                "date": voucher.date.isoformat(),
                "signed_amount": amount,
                "description": entry.description,
            }
        )

    unmatched_bank: list[dict[str, Any]] = []
    for txn in all_bank:
        if str(txn.id) in matched_bank_ids:
            continue
        signed = txn.amount if txn.direction == "Inflow" else -float(txn.amount)
        unmatched_bank.append(
            {
                "bank_transaction_id": str(txn.id),
                "date": txn.date.isoformat(),
                "signed_amount": signed,
                "description": txn.description,
            }
        )

    unmatched_internal = [
        row for row in all_internal if row["entry_id"] not in matched_entry_ids
    ]

    missing_bank = unmatched_bank
    missing_internal = unmatched_internal

    difference = compute_difference(unmatched_bank, unmatched_internal)

    return {
        "session_id": session_id,
        "period_code": session.period_code,
        "status": session.status,
        "matched": matched,
        "unmatched": {
            "bank": unmatched_bank,
            "internal": unmatched_internal,
        },
        "missing": {
            "bank_only": missing_bank,
            "internal_only": missing_internal,
        },
        "difference": difference,
    }


async def get_difference(
    db: AsyncSession,
    *,
    account_set_id: str,
    session_id: str,
) -> dict[str, Any]:
    """Return reconciliation difference (Req 5.5)."""
    report = await get_reconciliation_report(
        db, account_set_id=account_set_id, session_id=session_id
    )
    return {
        "session_id": session_id,
        "difference": report["difference"],
        "unmatched_bank_count": len(report["unmatched"]["bank"]),
        "unmatched_internal_count": len(report["unmatched"]["internal"]),
    }


async def complete_reconciliation(
    db: AsyncSession,
    *,
    account_set_id: str,
    session_id: str,
    user_id: str,
) -> dict[str, Any]:
    session = await _get_session(db, account_set_id=account_set_id, session_id=session_id)
    session.status = "Completed"
    await db.flush()

    diff = await get_difference(db, account_set_id=account_set_id, session_id=session_id)
    await write_tenant_audit(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        action="reconciliation.complete",
        entity_type="ReconciliationSession",
        entity_id=session_id,
        new_value={"difference": diff["difference"]},
    )
    return {"session_id": session_id, "status": session.status, **diff}
