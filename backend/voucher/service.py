"""
Voucher Engine service.

Implements double-entry bookkeeping enforcement, sequential numbering,
aux dimension validation, tenant audit logging, and Redis Streams event publishing.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.account import Account
from models.tenant_audit import TenantAuditLog
from models.voucher import Voucher, VoucherAttachment, VoucherEntry

logger = logging.getLogger(__name__)

# ── Redis client (lazy singleton) ─────────────────────────────────────────────

_redis_client: aioredis.Redis | None = None

VOUCHER_STREAM_KEY = "voucher:approved"


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = aioredis.from_url(redis_url, decode_responses=True)
    return _redis_client


# ── Voucher status constants ──────────────────────────────────────────────────

STATUS_DRAFT = "Draft"
STATUS_PENDING_REVIEW = "PendingReview"
STATUS_APPROVED = "Approved"
STATUS_REJECTED = "Rejected"
STATUS_DELETED = "Deleted"

VALID_TYPES = {"Receipt", "Payment", "Transfer"}

EDITABLE_STATUSES = {STATUS_DRAFT, STATUS_REJECTED}


# ── Validation helpers (unit-tested) ───────────────────────────────────────────


def _to_decimal(amount: float | Decimal | int) -> Decimal:
    return Decimal(str(amount))


def validate_entry_sides(entries: list[dict[str, Any]]) -> None:
    """Require at least one debit line and one credit line with positive amounts."""
    has_debit = any(_to_decimal(e.get("debit_amount", 0)) > 0 for e in entries)
    has_credit = any(_to_decimal(e.get("credit_amount", 0)) > 0 for e in entries)
    if not has_debit or not has_credit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Voucher must have at least one debit entry and one credit entry.",
        )


def validate_balance(entries: list[dict[str, Any]]) -> tuple[Decimal, Decimal]:
    """Validate sum(debits) == sum(credits). Returns (total_debits, total_credits)."""
    total_debits = sum(_to_decimal(e.get("debit_amount", 0)) for e in entries)
    total_credits = sum(_to_decimal(e.get("credit_amount", 0)) for e in entries)
    if total_debits != total_credits:
        imbalance = abs(total_debits - total_credits)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Debit and credit totals do not balance.",
                "total_debits": float(total_debits),
                "total_credits": float(total_credits),
                "imbalance_amount": float(imbalance),
            },
        )
    return total_debits, total_credits


def validate_aux_dimensions(
    entries: list[dict[str, Any]],
    accounts_by_code: dict[str, Account],
) -> None:
    """Reject entries missing required auxiliary dimension values."""
    missing: list[dict[str, str]] = []
    for entry in entries:
        code = entry.get("account_code", "")
        account = accounts_by_code.get(code)
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown account code: {code}",
            )
        required_dims: list = account.aux_dimensions or []
        if not required_dims:
            continue
        values = entry.get("aux_dimension_values") or {}
        for dim in required_dims:
            if not values.get(dim):
                missing.append({"account_code": code, "dimension": dim})
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Missing required auxiliary dimension values.",
                "missing": missing,
            },
        )


# ── Sequential numbering ──────────────────────────────────────────────────────


async def _next_voucher_number(
    account_set_id: str, period_code: str, db: AsyncSession
) -> int:
    """Next sequential number for (account_set_id, period_code).

    Deleted vouchers retain their number (tombstone) — MAX includes all rows.
    """
    result = await db.execute(
        select(func.max(Voucher.voucher_number)).where(
            Voucher.account_set_id == account_set_id,
            Voucher.period_code == period_code,
        )
    )
    current_max: int | None = result.scalar_one_or_none()
    return 1 if current_max is None else current_max + 1


# ── Internal helpers ──────────────────────────────────────────────────────────


def _assert_status(voucher: Voucher, allowed: set[str], action: str) -> None:
    if voucher.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot {action} voucher in status '{voucher.status}'.",
        )


async def _load_accounts(
    account_set_id: str, codes: set[str], db: AsyncSession
) -> dict[str, Account]:
    if not codes:
        return {}
    result = await db.execute(
        select(Account).where(
            Account.account_set_id == account_set_id,
            Account.code.in_(codes),
        )
    )
    accounts = list(result.scalars().all())
    return {a.code: a for a in accounts}


async def _get_voucher(
    account_set_id: str,
    voucher_id: str,
    db: AsyncSession,
) -> Voucher:
    return await get_voucher(db, account_set_id=account_set_id, voucher_id=voucher_id)


async def write_tenant_audit(
    db: AsyncSession,
    *,
    account_set_id: str,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> TenantAuditLog:
    entry = TenantAuditLog(
        account_set_id=account_set_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    return entry


async def _publish_voucher_approved(voucher: Voucher, entries: list[VoucherEntry]) -> None:
    """Publish voucher-approved event to Redis Streams for Ledger Engine."""
    try:
        redis = _get_redis()
        payload = {
            "voucher_id": str(voucher.id),
            "account_set_id": str(voucher.account_set_id),
            "period_code": voucher.period_code,
            "voucher_number": str(voucher.voucher_number),
            "type": voucher.type,
            "date": voucher.date.isoformat(),
            "approved_at": (
                voucher.reviewed_at.isoformat() if voucher.reviewed_at else ""
            ),
            "entries": json.dumps(
                [
                    {
                        "entry_id": str(e.id),
                        "account_code": e.account_code,
                        "debit_amount": float(e.debit_amount),
                        "credit_amount": float(e.credit_amount),
                        "description": e.description,
                        "aux_dimension_values": e.aux_dimension_values or {},
                        "sequence": e.sequence,
                    }
                    for e in entries
                ]
            ),
        }
        await redis.xadd(VOUCHER_STREAM_KEY, payload)
        logger.info(
            "Published voucher-approved event voucher_id=%s account_set_id=%s",
            voucher.id,
            voucher.account_set_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to publish voucher-approved event: %s", exc)


def _entry_dicts_from_models(entries: list[VoucherEntry]) -> list[dict[str, Any]]:
    return [
        {
            "account_code": e.account_code,
            "debit_amount": float(e.debit_amount),
            "credit_amount": float(e.credit_amount),
            "description": e.description,
            "aux_dimension_values": e.aux_dimension_values or {},
            "sequence": e.sequence,
        }
        for e in entries
    ]


async def _replace_entries(
    voucher: Voucher,
    entries_data: list[dict[str, Any]],
    db: AsyncSession,
) -> list[VoucherEntry]:
    await db.execute(delete(VoucherEntry).where(VoucherEntry.voucher_id == voucher.id))
    new_entries: list[VoucherEntry] = []
    for idx, raw in enumerate(entries_data):
        entry = VoucherEntry(
            voucher_id=voucher.id,
            account_code=raw["account_code"],
            debit_amount=raw.get("debit_amount", 0),
            credit_amount=raw.get("credit_amount", 0),
            description=raw.get("description", ""),
            aux_dimension_values=raw.get("aux_dimension_values") or {},
            sequence=raw.get("sequence", idx),
        )
        db.add(entry)
        new_entries.append(entry)
    await db.flush()
    return new_entries


# ── Public API ────────────────────────────────────────────────────────────────


async def create_voucher(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    voucher_type: str,
    voucher_date: date,
    entries: list[dict[str, Any]],
    attachments: list[dict[str, Any]],
    created_by_user_id: str,
) -> Voucher:
    """Create a draft voucher with sequential number and entries."""
    if voucher_type not in VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid voucher type. Must be one of: {', '.join(sorted(VALID_TYPES))}.",
        )
    if len(entries) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Voucher must have at least two entries.",
        )
    validate_entry_sides(entries)

    from period_end.periods import is_period_closed

    if await is_period_closed(db, account_set_id, period_code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Period {period_code} is closed. No new vouchers may be created.",
        )

    voucher_number = await _next_voucher_number(account_set_id, period_code, db)
    voucher = Voucher(
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_number=voucher_number,
        type=voucher_type,
        date=voucher_date,
        status=STATUS_DRAFT,
        created_by=created_by_user_id,
    )
    db.add(voucher)
    await db.flush()

    await _replace_entries(voucher, entries, db)

    for att in attachments:
        db.add(
            VoucherAttachment(
                voucher_id=voucher.id,
                file_key=att["file_key"],
                filename=att["filename"],
            )
        )
    await db.flush()
    await db.refresh(voucher)
    return voucher


async def get_voucher(
    db: AsyncSession,
    *,
    account_set_id: str,
    voucher_id: str,
) -> Voucher:
    result = await db.execute(
        select(Voucher)
        .where(
            Voucher.id == voucher_id,
            Voucher.account_set_id == account_set_id,
            Voucher.status != STATUS_DELETED,
        )
        .options(selectinload(Voucher.entries), selectinload(Voucher.attachments))  # type: ignore[arg-type]
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voucher not found.")
    return voucher


async def list_vouchers(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str | None = None,
    status_filter: str | None = None,
) -> list[Voucher]:
    stmt = select(Voucher).where(
        Voucher.account_set_id == account_set_id,
        Voucher.status != STATUS_DELETED,
    )
    if period_code:
        stmt = stmt.where(Voucher.period_code == period_code)
    if status_filter:
        stmt = stmt.where(Voucher.status == status_filter)
    stmt = stmt.order_by(Voucher.period_code, Voucher.voucher_number)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_voucher(
    db: AsyncSession,
    *,
    account_set_id: str,
    voucher_id: str,
    voucher_date: date | None = None,
    entries: list[dict[str, Any]] | None = None,
) -> Voucher:
    """Edit a draft or rejected voucher (rejected → draft on edit)."""
    voucher = await _get_voucher(account_set_id, voucher_id, db)
    _assert_status(voucher, EDITABLE_STATUSES, "edit")

    from period_end.periods import is_period_closed

    if await is_period_closed(db, account_set_id, voucher.period_code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Period {voucher.period_code} is closed. Vouchers cannot be modified.",
        )

    if voucher.status == STATUS_REJECTED:
        voucher.status = STATUS_DRAFT
        voucher.rejection_reason = None
        voucher.reviewed_by = None
        voucher.reviewed_at = None

    if voucher_date is not None:
        voucher.date = voucher_date

    if entries is not None:
        if len(entries) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Voucher must have at least two entries.",
            )
        validate_entry_sides(entries)
        await _replace_entries(voucher, entries, db)

    voucher.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_voucher(db, account_set_id=account_set_id, voucher_id=voucher_id)


async def save_voucher(
    db: AsyncSession,
    *,
    account_set_id: str,
    voucher_id: str,
) -> dict[str, Any]:
    """Validate debit/credit balance and auxiliary dimensions."""
    voucher = await _get_voucher(account_set_id, voucher_id, db)
    _assert_status(voucher, EDITABLE_STATUSES, "save")

    result = await db.execute(
        select(VoucherEntry).where(VoucherEntry.voucher_id == voucher.id)
    )
    entries = list(result.scalars().all())
    if len(entries) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Voucher must have at least two entries.",
        )

    entry_dicts = _entry_dicts_from_models(entries)
    validate_entry_sides(entry_dicts)
    validate_balance(entry_dicts)

    codes = {e.account_code for e in entries}
    accounts = await _load_accounts(account_set_id, codes, db)
    validate_aux_dimensions(entry_dicts, accounts)

    voucher.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "valid": True,
        "voucher_id": str(voucher.id),
        "message": "Voucher saved and validated successfully.",
    }


async def submit_for_review(
    db: AsyncSession,
    *,
    account_set_id: str,
    voucher_id: str,
) -> Voucher:
    """Submit after successful validation."""
    await save_voucher(db, account_set_id=account_set_id, voucher_id=voucher_id)
    voucher = await _get_voucher(account_set_id, voucher_id, db)
    _assert_status(voucher, {STATUS_DRAFT}, "submit for review")
    voucher.status = STATUS_PENDING_REVIEW
    voucher.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_voucher(db, account_set_id=account_set_id, voucher_id=voucher_id)


async def approve_voucher(
    db: AsyncSession,
    *,
    account_set_id: str,
    voucher_id: str,
    reviewer_id: str,
) -> Voucher:
    voucher = await _get_voucher(account_set_id, voucher_id, db)
    _assert_status(voucher, {STATUS_PENDING_REVIEW}, "approve")

    voucher.status = STATUS_APPROVED
    voucher.reviewed_by = reviewer_id
    voucher.reviewed_at = datetime.now(timezone.utc)
    voucher.rejection_reason = None
    voucher.updated_at = datetime.now(timezone.utc)
    await db.flush()

    result = await db.execute(
        select(VoucherEntry).where(VoucherEntry.voucher_id == voucher.id)
    )
    entries = list(result.scalars().all())
    await _publish_voucher_approved(voucher, entries)

    return await get_voucher(db, account_set_id=account_set_id, voucher_id=voucher_id)


async def reject_voucher(
    db: AsyncSession,
    *,
    account_set_id: str,
    voucher_id: str,
    reviewer_id: str,
    reason: str,
) -> Voucher:
    voucher = await _get_voucher(account_set_id, voucher_id, db)
    _assert_status(voucher, {STATUS_PENDING_REVIEW}, "reject")

    voucher.status = STATUS_REJECTED
    voucher.reviewed_by = reviewer_id
    voucher.reviewed_at = datetime.now(timezone.utc)
    voucher.rejection_reason = reason
    voucher.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_voucher(db, account_set_id=account_set_id, voucher_id=voucher_id)


async def delete_voucher(
    db: AsyncSession,
    *,
    account_set_id: str,
    voucher_id: str,
    user_id: str,
    ip_address: str | None = None,
) -> TenantAuditLog:
    """Tombstone delete — retains voucher_number, writes audit log."""
    voucher = await _get_voucher(account_set_id, voucher_id, db)
    _assert_status(voucher, EDITABLE_STATUSES, "delete")

    old_snapshot = {
        "id": str(voucher.id),
        "voucher_number": voucher.voucher_number,
        "period_code": voucher.period_code,
        "type": voucher.type,
        "status": voucher.status,
    }
    voucher.status = STATUS_DELETED
    voucher.updated_at = datetime.now(timezone.utc)
    await db.flush()

    audit = await write_tenant_audit(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        action="voucher.delete",
        entity_type="voucher",
        entity_id=str(voucher.id),
        old_value=old_snapshot,
        new_value={"status": STATUS_DELETED},
        ip_address=ip_address,
    )
    return audit


async def _assert_batch_same_period(
    db: AsyncSession,
    account_set_id: str,
    voucher_ids: list[str],
) -> None:
    result = await db.execute(
        select(Voucher.period_code).where(
            Voucher.account_set_id == account_set_id,
            Voucher.id.in_(voucher_ids),
        )
    )
    periods = {row[0] for row in result.all()}
    if len(periods) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Batch operations must target vouchers in the same period.",
        )


async def batch_approve(
    db: AsyncSession,
    *,
    account_set_id: str,
    voucher_ids: list[str],
    reviewer_id: str,
) -> dict[str, Any]:
    await _assert_batch_same_period(db, account_set_id, voucher_ids)
    succeeded: list[str] = []
    failed: list[str] = []
    for vid in voucher_ids:
        try:
            await approve_voucher(
                db,
                account_set_id=account_set_id,
                voucher_id=vid,
                reviewer_id=reviewer_id,
            )
            succeeded.append(vid)
        except HTTPException:
            failed.append(vid)
    return {
        "succeeded": succeeded,
        "failed": failed,
        "message": f"Approved {len(succeeded)} of {len(voucher_ids)} vouchers.",
    }


async def batch_delete(
    db: AsyncSession,
    *,
    account_set_id: str,
    voucher_ids: list[str],
    user_id: str,
    ip_address: str | None = None,
) -> dict[str, Any]:
    await _assert_batch_same_period(db, account_set_id, voucher_ids)
    succeeded: list[str] = []
    failed: list[str] = []
    for vid in voucher_ids:
        try:
            await delete_voucher(
                db,
                account_set_id=account_set_id,
                voucher_id=vid,
                user_id=user_id,
                ip_address=ip_address,
            )
            succeeded.append(vid)
        except HTTPException:
            failed.append(vid)
    return {
        "succeeded": succeeded,
        "failed": failed,
        "message": f"Deleted {len(succeeded)} of {len(voucher_ids)} vouchers.",
    }
