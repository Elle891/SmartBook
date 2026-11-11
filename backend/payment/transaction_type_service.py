"""
Payment Transaction Type configuration service (Task 24a).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.payment import PaymentTransactionType
from voucher.service import write_tenant_audit

STANDARD_TYPE_NAME = "Standard"
ALWAYS_MANUAL_FIELDS = ("instruct_mode", "authorise_mode", "settle_mode")
VALID_MODES = frozenset({"Auto", "Manual"})


class TransactionTypeValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def validate_stage_modes(
    *,
    instruct_mode: str,
    authorise_mode: str,
    settle_mode: str,
    prepare_mode: str = "Auto",
    check_mode: str = "Auto",
    confirm_mode: str = "Auto",
) -> None:
    """Instruct, Authorise, and Settle must always be Manual (Req 30.4)."""
    for field, value in (
        ("prepare_mode", prepare_mode),
        ("instruct_mode", instruct_mode),
        ("check_mode", check_mode),
        ("authorise_mode", authorise_mode),
        ("confirm_mode", confirm_mode),
        ("settle_mode", settle_mode),
    ):
        if value not in VALID_MODES:
            raise TransactionTypeValidationError(
                f"{field} must be Auto or Manual, got '{value}'."
            )

    for field in ALWAYS_MANUAL_FIELDS:
        value = locals()[field]
        if value != "Manual":
            raise TransactionTypeValidationError(
                f"{field} must always be Manual (cannot be Auto)."
            )


def _serialize(txn_type: PaymentTransactionType) -> dict[str, Any]:
    return {
        "id": str(txn_type.id),
        "account_set_id": str(txn_type.account_set_id),
        "name": txn_type.name,
        "prepare_mode": txn_type.prepare_mode,
        "instruct_mode": txn_type.instruct_mode,
        "check_mode": txn_type.check_mode,
        "authorise_mode": txn_type.authorise_mode,
        "confirm_mode": txn_type.confirm_mode,
        "settle_mode": txn_type.settle_mode,
        "is_active": txn_type.is_active,
        "created_at": txn_type.created_at.isoformat() if txn_type.created_at else None,
    }


def _snapshot(txn_type: PaymentTransactionType) -> dict[str, Any]:
    return {
        "name": txn_type.name,
        "prepare_mode": txn_type.prepare_mode,
        "instruct_mode": txn_type.instruct_mode,
        "check_mode": txn_type.check_mode,
        "authorise_mode": txn_type.authorise_mode,
        "confirm_mode": txn_type.confirm_mode,
        "settle_mode": txn_type.settle_mode,
        "is_active": txn_type.is_active,
    }


async def get_transaction_type(
    db: AsyncSession,
    *,
    account_set_id: str,
    type_id: str,
    active_only: bool = True,
) -> PaymentTransactionType | None:
    stmt = select(PaymentTransactionType).where(
        PaymentTransactionType.id == type_id,
        PaymentTransactionType.account_set_id == account_set_id,
    )
    if active_only:
        stmt = stmt.where(PaymentTransactionType.is_active.is_(True))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_transaction_types(
    db: AsyncSession,
    *,
    account_set_id: str,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    stmt = select(PaymentTransactionType).where(
        PaymentTransactionType.account_set_id == account_set_id
    )
    if not include_inactive:
        stmt = stmt.where(PaymentTransactionType.is_active.is_(True))
    stmt = stmt.order_by(PaymentTransactionType.name.asc())
    result = await db.execute(stmt)
    return [_serialize(t) for t in result.scalars()]


async def get_default_transaction_type(
    db: AsyncSession,
    *,
    account_set_id: str,
) -> dict[str, Any]:
    """Return the Standard active transaction type (Req 30.5 default)."""
    txn_type = await ensure_standard_transaction_type(db, account_set_id=account_set_id)
    if not txn_type.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Default Standard transaction type is deactivated.",
        )
    return _serialize(txn_type)


async def ensure_standard_transaction_type(
    db: AsyncSession,
    *,
    account_set_id: str,
) -> PaymentTransactionType:
    """Seed default Standard type on tenant provisioning (Req 30.3)."""
    result = await db.execute(
        select(PaymentTransactionType).where(
            PaymentTransactionType.account_set_id == account_set_id,
            PaymentTransactionType.name == STANDARD_TYPE_NAME,
        )
    )
    txn_type = result.scalar_one_or_none()
    if txn_type is not None:
        return txn_type

    txn_type = PaymentTransactionType(
        account_set_id=uuid.UUID(account_set_id),
        name=STANDARD_TYPE_NAME,
        prepare_mode="Auto",
        instruct_mode="Manual",
        check_mode="Auto",
        authorise_mode="Manual",
        confirm_mode="Auto",
        settle_mode="Manual",
        is_active=True,
    )
    db.add(txn_type)
    await db.flush()
    return txn_type


async def save_transaction_type(
    db: AsyncSession,
    *,
    account_set_id: str,
    user_id: str,
    name: str,
    prepare_mode: str = "Auto",
    instruct_mode: str = "Manual",
    check_mode: str = "Auto",
    authorise_mode: str = "Manual",
    confirm_mode: str = "Auto",
    settle_mode: str = "Manual",
    type_id: str | None = None,
) -> dict[str, Any]:
    """Create or update a transaction type (Admin only — enforced at route)."""
    try:
        validate_stage_modes(
            prepare_mode=prepare_mode,
            instruct_mode=instruct_mode,
            check_mode=check_mode,
            authorise_mode=authorise_mode,
            confirm_mode=confirm_mode,
            settle_mode=settle_mode,
        )
    except TransactionTypeValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc

    old_value = None
    if type_id:
        result = await db.execute(
            select(PaymentTransactionType).where(
                PaymentTransactionType.id == type_id,
                PaymentTransactionType.account_set_id == account_set_id,
            )
        )
        txn_type = result.scalar_one_or_none()
        if txn_type is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction type not found.")
        old_value = _snapshot(txn_type)
        txn_type.name = name
        txn_type.prepare_mode = prepare_mode
        txn_type.instruct_mode = instruct_mode
        txn_type.check_mode = check_mode
        txn_type.authorise_mode = authorise_mode
        txn_type.confirm_mode = confirm_mode
        txn_type.settle_mode = settle_mode
    else:
        dup = await db.execute(
            select(PaymentTransactionType).where(
                PaymentTransactionType.account_set_id == account_set_id,
                PaymentTransactionType.name == name,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Transaction type '{name}' already exists.",
            )
        txn_type = PaymentTransactionType(
            account_set_id=uuid.UUID(account_set_id),
            name=name,
            prepare_mode=prepare_mode,
            instruct_mode=instruct_mode,
            check_mode=check_mode,
            authorise_mode=authorise_mode,
            confirm_mode=confirm_mode,
            settle_mode=settle_mode,
            is_active=True,
        )
        db.add(txn_type)

    await db.flush()
    new_value = _snapshot(txn_type)

    await write_tenant_audit(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        action="payment_transaction_type.save",
        entity_type="PaymentTransactionType",
        entity_id=str(txn_type.id),
        old_value=old_value,
        new_value=new_value,
    )

    return _serialize(txn_type)


async def deactivate_transaction_type(
    db: AsyncSession,
    *,
    account_set_id: str,
    type_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Deactivate type; existing payments unaffected (Req 30.11)."""
    result = await db.execute(
        select(PaymentTransactionType).where(
            PaymentTransactionType.id == type_id,
            PaymentTransactionType.account_set_id == account_set_id,
        )
    )
    txn_type = result.scalar_one_or_none()
    if txn_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction type not found.")

    if txn_type.name == STANDARD_TYPE_NAME and txn_type.is_active:
        active_count = await db.execute(
            select(PaymentTransactionType).where(
                PaymentTransactionType.account_set_id == account_set_id,
                PaymentTransactionType.is_active.is_(True),
            )
        )
        if len(list(active_count.scalars())) <= 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot deactivate the only active transaction type.",
            )

    old_value = _snapshot(txn_type)
    txn_type.is_active = False
    await db.flush()

    await write_tenant_audit(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        action="payment_transaction_type.deactivate",
        entity_type="PaymentTransactionType",
        entity_id=str(txn_type.id),
        old_value=old_value,
        new_value=_snapshot(txn_type),
    )

    return _serialize(txn_type)


async def update_transaction_type(
    db: AsyncSession,
    *,
    account_set_id: str,
    type_id: str,
    user_id: str,
    name: str | None = None,
    prepare_mode: str | None = None,
    check_mode: str | None = None,
    confirm_mode: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    """PATCH handler — partial update; deactivation via is_active=False."""
    if is_active is False:
        return await deactivate_transaction_type(
            db, account_set_id=account_set_id, type_id=type_id, user_id=user_id
        )

    result = await db.execute(
        select(PaymentTransactionType).where(
            PaymentTransactionType.id == type_id,
            PaymentTransactionType.account_set_id == account_set_id,
        )
    )
    txn_type = result.scalar_one_or_none()
    if txn_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction type not found.")

    return await save_transaction_type(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        type_id=type_id,
        name=name or txn_type.name,
        prepare_mode=prepare_mode or txn_type.prepare_mode,
        instruct_mode=txn_type.instruct_mode,
        check_mode=check_mode or txn_type.check_mode,
        authorise_mode=txn_type.authorise_mode,
        confirm_mode=confirm_mode or txn_type.confirm_mode,
        settle_mode=txn_type.settle_mode,
    )
