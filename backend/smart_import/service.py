"""
Smart Import service — file import, mapping, voucher batch generation.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.smart_import import (
    SESSION_STATUS_CONFIRMED,
    SESSION_STATUS_PARSED,
    TXN_STATUS_CONFIRMED,
    TXN_STATUS_PENDING,
    TXN_STATUS_SKIPPED,
    TXN_STATUS_SKIPPED_DUPLICATE,
    ImportSession,
    ImportTransaction,
)
from period_end.periods import assert_period_open
from smart_import.mappings import (
    DIRECTION_INFLOW,
    build_voucher_entries,
    suggest_account_mapping,
)
from smart_import.parser import (
    FORMAT_AUTO,
    ParseError,
    dedup_key,
    parse_file_content,
)
from voucher.service import create_voucher

logger = logging.getLogger(__name__)


def _period_code_from_date(txn_date: date) -> str:
    return f"{txn_date.year}{txn_date.month:02d}"


async def _existing_dedup_keys(
    db: AsyncSession,
    account_set_id: str,
) -> set[tuple[str, str, str, str]]:
    result = await db.execute(
        select(ImportTransaction).where(
            ImportTransaction.account_set_id == account_set_id,
            ImportTransaction.status.in_(
                (TXN_STATUS_PENDING, TXN_STATUS_CONFIRMED, TXN_STATUS_SKIPPED_DUPLICATE)
            ),
        )
    )
    rows = result.scalars().all()
    return {
        dedup_key(
            account_set_id,
            row.txn_date,
            float(row.amount),
            row.reference_number,
        )
        for row in rows
    }


async def import_file(
    db: AsyncSession,
    *,
    account_set_id: str,
    file_name: str,
    content: bytes,
    file_format: str = FORMAT_AUTO,
    user_id: str,
) -> ImportSession:
    """Upload and parse a transaction file, persisting session + rows (Req 19.1–19.3)."""
    try:
        parsed = parse_file_content(
            file_name=file_name, content=content, file_format=file_format
        )
    except ParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No valid transactions found in file.",
        )

    detected_format = file_format if file_format != FORMAT_AUTO else _infer_stored_format(file_name)
    session = ImportSession(
        account_set_id=account_set_id,
        file_name=file_name,
        file_format=detected_format,
        status=SESSION_STATUS_PARSED,
        created_by=user_id,
    )
    db.add(session)
    await db.flush()

    existing_keys = await _existing_dedup_keys(db, account_set_id)
    skipped = 0
    for txn in parsed:
        key = dedup_key(account_set_id, txn.txn_date, txn.amount, txn.reference_number)
        suggestion = suggest_account_mapping(
            direction=txn.direction,
            counterparty=txn.counterparty,
            description=txn.description,
        )
        if key in existing_keys:
            status_value = TXN_STATUS_SKIPPED_DUPLICATE
            skipped += 1
        else:
            status_value = TXN_STATUS_PENDING
            existing_keys.add(key)

        row = ImportTransaction(
            session_id=session.id,
            account_set_id=account_set_id,
            txn_date=txn.txn_date,
            amount=txn.amount,
            direction=txn.direction,
            counterparty=txn.counterparty,
            description=txn.description,
            reference_number=txn.reference_number,
            suggested_debit_account=suggestion.debit_account,
            suggested_credit_account=suggestion.credit_account,
            status=status_value,
        )
        db.add(row)

    session.total_records = len(parsed)
    session.records_skipped = skipped
    await db.flush()
    return session


def _infer_stored_format(file_name: str) -> str:
    lower = file_name.lower()
    if "wechat" in lower or "微信" in file_name:
        return "wechat_csv"
    if "alipay" in lower or "支付宝" in file_name:
        return "alipay_csv"
    if lower.endswith((".xls", ".xlsx")):
        return "bank_xls"
    return "bank_csv"


async def parse_transactions(
    db: AsyncSession,
    *,
    session_id: str,
    account_set_id: str,
) -> list[dict[str, Any]]:
    """Return parsed transactions for a session with mapping suggestions."""
    session = await _get_session(db, session_id, account_set_id)
    result = await db.execute(
        select(ImportTransaction)
        .where(ImportTransaction.session_id == session.id)
        .order_by(ImportTransaction.txn_date, ImportTransaction.reference_number)
    )
    rows = result.scalars().all()
    return [_transaction_to_dict(row) for row in rows]


def suggest_account_mapping_for_transaction(
    *,
    direction: str,
    counterparty: str,
    description: str,
) -> dict[str, Any]:
    """Public wrapper for keyword mapping (Req 19.4)."""
    suggestion = suggest_account_mapping(
        direction=direction,
        counterparty=counterparty,
        description=description,
    )
    return {
        "debit_account": suggestion.debit_account,
        "credit_account": suggestion.credit_account,
        "matched_keyword": suggestion.matched_keyword,
        "confidence": suggestion.confidence,
    }


async def confirm_mapping(
    db: AsyncSession,
    *,
    session_id: str,
    account_set_id: str,
    user_id: str,
    mappings: list[dict[str, Any]],
    bank_account: str = "1001",
) -> dict[str, Any]:
    """Confirm account mappings and generate vouchers (Req 19.5)."""
    session = await _get_session(db, session_id, account_set_id)
    vouchers_created = 0
    skipped = 0
    voucher_ids: list[str] = []

    for item in mappings:
        txn_id = str(item.get("transaction_id", ""))
        skip = bool(item.get("skip", False))
        if not txn_id:
            continue

        result = await db.execute(
            select(ImportTransaction).where(
                ImportTransaction.id == txn_id,
                ImportTransaction.session_id == session.id,
            )
        )
        txn = result.scalar_one_or_none()
        if txn is None:
            continue

        if txn.status == TXN_STATUS_SKIPPED_DUPLICATE:
            skipped += 1
            continue

        if skip:
            txn.status = TXN_STATUS_SKIPPED
            skipped += 1
            continue

        if txn.status == TXN_STATUS_CONFIRMED:
            continue

        debit_account = item.get("debit_account") or txn.suggested_debit_account
        credit_account = item.get("credit_account") or txn.suggested_credit_account
        period_code = item.get("period_code") or _period_code_from_date(txn.txn_date)

        await assert_period_open(db, account_set_id, period_code)

        description = txn.description or f"Import {txn.reference_number or txn.counterparty}"
        entries = build_voucher_entries(
            debit_account=debit_account,
            credit_account=credit_account,
            amount=float(txn.amount),
            description=description,
        )
        voucher_type = "Receipt" if txn.direction == DIRECTION_INFLOW else "Payment"
        voucher = await create_voucher(
            db,
            account_set_id=account_set_id,
            period_code=period_code,
            voucher_type=voucher_type,
            voucher_date=txn.txn_date,
            entries=entries,
            attachments=[],
            created_by_user_id=user_id,
        )

        txn.mapped_debit_account = debit_account
        txn.mapped_credit_account = credit_account
        txn.status = TXN_STATUS_CONFIRMED
        txn.voucher_id = voucher.id
        vouchers_created += 1
        voucher_ids.append(str(voucher.id))

    session.vouchers_generated += vouchers_created
    session.records_skipped += skipped
    session.status = SESSION_STATUS_CONFIRMED
    await db.flush()

    return {
        "session_id": str(session.id),
        "vouchers_generated": vouchers_created,
        "records_skipped": skipped,
        "voucher_ids": voucher_ids,
        "summary": await get_import_summary(db, session_id=str(session.id), account_set_id=account_set_id),
    }


async def get_import_summary(
    db: AsyncSession,
    *,
    session_id: str,
    account_set_id: str,
) -> dict[str, Any]:
    """Import batch summary (Req 19.7)."""
    session = await _get_session(db, session_id, account_set_id)
    return {
        "session_id": str(session.id),
        "file_name": session.file_name,
        "file_format": session.file_format,
        "status": session.status,
        "total_records_processed": session.total_records,
        "vouchers_generated": session.vouchers_generated,
        "records_skipped": session.records_skipped,
    }


async def _get_session(
    db: AsyncSession,
    session_id: str,
    account_set_id: str,
) -> ImportSession:
    result = await db.execute(
        select(ImportSession).where(
            ImportSession.id == session_id,
            ImportSession.account_set_id == account_set_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import session not found.")
    return session


def _transaction_to_dict(row: ImportTransaction) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "txn_date": row.txn_date.isoformat(),
        "amount": float(row.amount),
        "direction": row.direction,
        "counterparty": row.counterparty,
        "description": row.description,
        "reference_number": row.reference_number,
        "suggested_debit_account": row.suggested_debit_account,
        "suggested_credit_account": row.suggested_credit_account,
        "status": row.status,
        "voucher_id": str(row.voucher_id) if row.voucher_id else None,
    }
