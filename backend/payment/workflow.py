"""
Payment settlement workflow engine.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.rbac import ROLE_ACCOUNT_SET_ADMIN, ROLE_SUPERVISOR
from bank.routing import ROUTING_SWIFT
from payment import clients, notifications, pain001
from payment.config import get_dual_auth_threshold
from payment.pain001 import build_pain001, generate_uetr, validate_required_fields
from payment.stages import (
    ACTION_AUTHORISE,
    ACTION_CHECK_APPROVE,
    ACTION_CHECK_REJECT,
    ACTION_CONFIRM,
    ACTION_INSTRUCT,
    ACTION_SETTLE,
    STAGE_AUTHORISED,
    STAGE_CHECKED,
    STAGE_CONFIRMED,
    STAGE_INSTRUCTED,
    STAGE_PENDING_SECOND,
    STAGE_PREPARE,
    STAGE_SETTLED,
    StageModeMap,
    WorkflowError,
    authorise_target_stage,
    is_transition_allowed,
    next_auto_stages,
    validate_role_for_action,
    validate_transition,
)
from payment import service as payment_svc
from payment.transaction_type_service import get_transaction_type
from models.payment import Payment, PaymentStageTransition, PaymentTransactionType
from voucher.service import write_tenant_audit

logger = logging.getLogger(__name__)

SYSTEM_TRIGGER = "system"


async def _get_payment(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment_id: str,
) -> Payment:
    result = await db.execute(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.account_set_id == account_set_id,
        )
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")
    return payment


async def _get_txn_type(db: AsyncSession, payment: Payment) -> PaymentTransactionType:
    txn_type = await get_transaction_type(
        db,
        account_set_id=str(payment.account_set_id),
        type_id=str(payment.transaction_type_id),
    )
    if txn_type is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Payment transaction type not found.")
    return txn_type


async def _record_transition(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment: Payment,
    from_stage: str,
    to_stage: str,
    triggered_by: str,
    reason: str | None = None,
    user_id: str | None = None,
) -> PaymentStageTransition:
    transition = PaymentStageTransition(
        payment_id=payment.id,
        from_stage=from_stage,
        to_stage=to_stage,
        triggered_by=triggered_by,
        reason=reason,
    )
    db.add(transition)
    payment.stage = to_stage
    payment.updated_at = datetime.now(timezone.utc)
    await db.flush()

    if user_id:
        await write_tenant_audit(
            db,
            account_set_id=account_set_id,
            user_id=user_id,
            action="payment.stage_transition",
            entity_type="Payment",
            entity_id=str(payment.id),
            old_value={"stage": from_stage},
            new_value={"stage": to_stage, "triggered_by": triggered_by, "reason": reason},
        )
    return transition


async def _auto_advance(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment: Payment,
    txn_type: PaymentTransactionType,
    role: str = ROLE_ACCOUNT_SET_ADMIN,
) -> list[str]:
    """Auto-advance through Auto-configured stages (Req 30.6)."""
    modes = StageModeMap.from_transaction_type(txn_type)
    advanced: list[str] = []
    while True:
        targets = next_auto_stages(modes, from_stage=payment.stage)
        if not targets:
            break
        target = targets[0]
        if target == STAGE_INSTRUCTED and payment.stage == STAGE_PREPARE:
            await instruct_payment(
                db,
                account_set_id=account_set_id,
                payment_id=str(payment.id),
                user_id=SYSTEM_TRIGGER,
                role=role,
                triggered_by=SYSTEM_TRIGGER,
            )
        elif target == STAGE_CHECKED and payment.stage == STAGE_INSTRUCTED:
            await check_payment(
                db,
                account_set_id=account_set_id,
                payment_id=str(payment.id),
                approved=True,
                user_id=SYSTEM_TRIGGER,
                role=ROLE_SUPERVISOR,
                triggered_by=SYSTEM_TRIGGER,
            )
        elif target == STAGE_CONFIRMED and payment.stage == STAGE_AUTHORISED:
            await confirm_payment(
                db,
                account_set_id=account_set_id,
                payment_id=str(payment.id),
                user_id=SYSTEM_TRIGGER,
                role=role,
                triggered_by=SYSTEM_TRIGGER,
            )
        elif target == STAGE_SETTLED and payment.stage == STAGE_CONFIRMED:
            await settle_payment(
                db,
                account_set_id=account_set_id,
                payment_id=str(payment.id),
                settlement_date=date.today(),
                user_id=SYSTEM_TRIGGER,
                role=role,
                triggered_by=SYSTEM_TRIGGER,
            )
        else:
            break
        advanced.append(payment.stage)
        if payment.stage == STAGE_SETTLED:
            break
    return advanced


async def initiate_payment_in_prepare(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment: Payment,
    txn_type: PaymentTransactionType,
    user_id: str,
    role: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Register a new payment in Prepare and auto-advance when Prepare is Auto."""
    await _record_transition(
        db,
        account_set_id=account_set_id,
        payment=payment,
        from_stage="Created",
        to_stage=STAGE_PREPARE,
        triggered_by=user_id,
        reason=reason,
        user_id=user_id,
    )
    advanced = await _auto_advance(
        db,
        account_set_id=account_set_id,
        payment=payment,
        txn_type=txn_type,
        role=role,
    )
    return {
        "payment_id": str(payment.id),
        "stage": payment.stage,
        "auto_advanced_stages": advanced,
    }


async def instruct_payment(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment_id: str,
    user_id: str,
    role: str,
    triggered_by: str | None = None,
) -> dict[str, Any]:
    payment = await _get_payment(db, account_set_id=account_set_id, payment_id=payment_id)
    validate_role_for_action(ACTION_INSTRUCT, role)
    validate_transition(payment.stage, STAGE_INSTRUCTED, action=ACTION_INSTRUCT, role=role)

    validate_required_fields(payment)
    payment.iso_pain001 = build_pain001(payment)
    if payment.routing_method == ROUTING_SWIFT:
        payment.uetr = generate_uetr()

    await _record_transition(
        db,
        account_set_id=account_set_id,
        payment=payment,
        from_stage=payment.stage,
        to_stage=STAGE_INSTRUCTED,
        triggered_by=triggered_by or user_id,
        user_id=user_id if triggered_by != SYSTEM_TRIGGER else None,
    )

    txn_type = await _get_txn_type(db, payment)
    await _auto_advance(db, account_set_id=account_set_id, payment=payment, txn_type=txn_type, role=role)

    return {"payment_id": payment_id, "stage": payment.stage, "uetr": payment.uetr}


async def check_payment(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment_id: str,
    approved: bool,
    user_id: str,
    role: str,
    rejection_reason: str | None = None,
    triggered_by: str | None = None,
) -> dict[str, Any]:
    payment = await _get_payment(db, account_set_id=account_set_id, payment_id=payment_id)
    txn_type = await _get_txn_type(db, payment)
    if txn_type.check_mode == "Manual" and triggered_by == SYSTEM_TRIGGER:
        raise WorkflowError("Check stage is Manual; system cannot auto-advance.")

    if approved:
        validate_role_for_action(ACTION_CHECK_APPROVE, role)
        validate_transition(payment.stage, STAGE_CHECKED, action=ACTION_CHECK_APPROVE, role=role)
        to_stage = STAGE_CHECKED
        reason = None
    else:
        validate_role_for_action(ACTION_CHECK_REJECT, role)
        validate_transition(payment.stage, STAGE_PREPARE, action=ACTION_CHECK_REJECT, role=role)
        to_stage = STAGE_PREPARE
        reason = rejection_reason or "Check rejected"
        notifications.notify_payment_rejection(
            account_set_id=account_set_id,
            payment_id=payment_id,
            created_by=str(payment.created_by),
            reason=reason,
            stage=STAGE_INSTRUCTED,
        )

    from_stage = payment.stage
    await _record_transition(
        db,
        account_set_id=account_set_id,
        payment=payment,
        from_stage=from_stage,
        to_stage=to_stage,
        triggered_by=triggered_by or user_id,
        reason=reason,
        user_id=user_id if triggered_by != SYSTEM_TRIGGER else None,
    )

    if approved:
        await _auto_advance(db, account_set_id=account_set_id, payment=payment, txn_type=txn_type, role=role)

    return {"payment_id": payment_id, "stage": payment.stage, "approved": approved}


async def authorise_payment(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment_id: str,
    user_id: str,
    role: str,
) -> dict[str, Any]:
    payment = await _get_payment(db, account_set_id=account_set_id, payment_id=payment_id)
    validate_role_for_action(ACTION_AUTHORISE, role)

    threshold = get_dual_auth_threshold(account_set_id)
    to_stage = authorise_target_stage(
        amount=float(payment.amount),
        threshold=threshold,
        current_stage=payment.stage,
        first_authoriser_id=str(payment.first_authoriser_id) if payment.first_authoriser_id else None,
        user_id=user_id,
    )

    if not is_transition_allowed(payment.stage, to_stage):
        raise WorkflowError(
            f"Cannot transition from {payment.stage} to {to_stage}.",
            details={"stage": payment.stage},
        )

    from_stage = payment.stage
    if to_stage == STAGE_PENDING_SECOND:
        payment.first_authoriser_id = uuid.UUID(user_id)
    elif to_stage == STAGE_AUTHORISED and from_stage == STAGE_PENDING_SECOND:
        pass
    elif to_stage == STAGE_AUTHORISED:
        payment.first_authoriser_id = uuid.UUID(user_id)

    await _record_transition(
        db,
        account_set_id=account_set_id,
        payment=payment,
        from_stage=from_stage,
        to_stage=to_stage,
        triggered_by=user_id,
        user_id=user_id,
    )

    txn_type = await _get_txn_type(db, payment)
    if payment.stage == STAGE_AUTHORISED:
        await _auto_advance(db, account_set_id=account_set_id, payment=payment, txn_type=txn_type, role=role)

    return {"payment_id": payment_id, "stage": payment.stage}


async def confirm_payment(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment_id: str,
    user_id: str,
    role: str,
    triggered_by: str | None = None,
) -> dict[str, Any]:
    payment = await _get_payment(db, account_set_id=account_set_id, payment_id=payment_id)
    txn_type = await _get_txn_type(db, payment)
    if txn_type.confirm_mode == "Manual" and triggered_by == SYSTEM_TRIGGER:
        raise WorkflowError("Confirm stage is Manual; system cannot auto-advance.")

    validate_role_for_action(ACTION_CONFIRM, role)
    validate_transition(payment.stage, STAGE_CONFIRMED, action=ACTION_CONFIRM, role=role)

    result = await clients.submit_payment_instruction(
        payment_id=payment_id,
        pain001=payment.iso_pain001 or "",
    )

    if not result.get("success"):
        reason = str(result.get("message", "Bank rejected payment"))
        await _record_transition(
            db,
            account_set_id=account_set_id,
            payment=payment,
            from_stage=payment.stage,
            to_stage=STAGE_PREPARE,
            triggered_by=triggered_by or user_id,
            reason=reason,
            user_id=user_id if triggered_by != SYSTEM_TRIGGER else None,
        )
        notifications.notify_payment_rejection(
            account_set_id=account_set_id,
            payment_id=payment_id,
            created_by=str(payment.created_by),
            reason=reason,
            stage=STAGE_AUTHORISED,
        )
        return {"payment_id": payment_id, "stage": payment.stage, "success": False, "message": reason}

    bank_ref = result.get("bank_reference")
    if bank_ref:
        payment.bank_reference = str(bank_ref)

    await _record_transition(
        db,
        account_set_id=account_set_id,
        payment=payment,
        from_stage=payment.stage,
        to_stage=STAGE_CONFIRMED,
        triggered_by=triggered_by or user_id,
        user_id=user_id if triggered_by != SYSTEM_TRIGGER else None,
    )

    await _auto_advance(db, account_set_id=account_set_id, payment=payment, txn_type=txn_type, role=role)
    return {"payment_id": payment_id, "stage": payment.stage, "success": True}


async def settle_payment(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment_id: str,
    settlement_date: date,
    user_id: str,
    role: str,
    triggered_by: str | None = None,
) -> dict[str, Any]:
    payment = await _get_payment(db, account_set_id=account_set_id, payment_id=payment_id)
    txn_type = await _get_txn_type(db, payment)
    if txn_type.settle_mode == "Manual" and triggered_by == SYSTEM_TRIGGER:
        raise WorkflowError("Settle stage is Manual; system cannot auto-advance.")

    validate_role_for_action(ACTION_SETTLE, role)
    validate_transition(payment.stage, STAGE_SETTLED, action=ACTION_SETTLE, role=role)

    payment.actual_settlement_date = settlement_date

    await _record_transition(
        db,
        account_set_id=account_set_id,
        payment=payment,
        from_stage=payment.stage,
        to_stage=STAGE_SETTLED,
        triggered_by=triggered_by or user_id,
        reason=f"settlement_date={settlement_date.isoformat()}",
        user_id=user_id if triggered_by != SYSTEM_TRIGGER else None,
    )
    return {"payment_id": payment_id, "stage": payment.stage, "settlement_date": settlement_date.isoformat()}


async def pay_now(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment_id: str,
    user_id: str,
    role: str,
) -> dict[str, Any]:
    """Immediately confirm an Authorised payment (Req 29.5)."""
    payment = await _get_payment(db, account_set_id=account_set_id, payment_id=payment_id)
    if payment.stage != STAGE_AUTHORISED:
        raise WorkflowError(
            "Pay Now requires payment to be in Authorised stage.",
            details={"stage": payment.stage},
        )
    return await confirm_payment(
        db,
        account_set_id=account_set_id,
        payment_id=payment_id,
        user_id=user_id,
        role=role,
    )


async def get_scheduling_queue(
    db: AsyncSession,
    *,
    account_set_id: str,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Payment)
        .where(
            Payment.account_set_id == account_set_id,
            Payment.stage.in_([STAGE_PREPARE, STAGE_INSTRUCTED]),
        )
        .order_by(
            Payment.scheduled_date.is_(None).asc(),
            Payment.scheduled_date.asc(),
            Payment.created_at.asc(),
        )
    )
    rows: list[dict[str, Any]] = []
    for p in result.scalars():
        txn_type = await get_transaction_type(
            db, account_set_id=account_set_id, type_id=str(p.transaction_type_id)
        )
        cutoff = payment_svc.get_settlement_cutoff_info(
            routing_method=p.routing_method,
            settlement_method=p.settlement_method,
        )
        rows.append(
            {
                "payment_id": str(p.id),
                "stage": p.stage,
                "amount": float(p.amount),
                "currency": p.currency,
                "payment_scope": p.payment_scope,
                "routing_method": p.routing_method,
                "settlement_method": p.settlement_method,
                "scheduled_date": p.scheduled_date.isoformat() if p.scheduled_date else None,
                "recipient_name": p.recipient_name,
                "transaction_type_id": str(p.transaction_type_id),
                "transaction_type_name": txn_type.name if txn_type else None,
                "cutoff_at_risk": bool(cutoff.get("cutoff_passed")),
                "cutoff": cutoff,
            }
        )
    return rows


async def get_authorised_payments(
    db: AsyncSession,
    *,
    account_set_id: str,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Payment)
        .where(
            Payment.account_set_id == account_set_id,
            Payment.stage == STAGE_AUTHORISED,
        )
        .order_by(
            Payment.scheduled_date.is_(None).asc(),
            Payment.scheduled_date.asc(),
            Payment.created_at.asc(),
        )
    )
    rows: list[dict[str, Any]] = []
    for p in result.scalars():
        txn_type = await get_transaction_type(
            db, account_set_id=account_set_id, type_id=str(p.transaction_type_id)
        )
        cutoff = payment_svc.get_settlement_cutoff_info(
            routing_method=p.routing_method,
            settlement_method=p.settlement_method,
        )
        rows.append(
            {
                "payment_id": str(p.id),
                "stage": p.stage,
                "amount": float(p.amount),
                "currency": p.currency,
                "payment_scope": p.payment_scope,
                "routing_method": p.routing_method,
                "settlement_method": p.settlement_method,
                "scheduled_date": p.scheduled_date.isoformat() if p.scheduled_date else None,
                "recipient_name": p.recipient_name,
                "transaction_type_id": str(p.transaction_type_id),
                "transaction_type_name": txn_type.name if txn_type else None,
                "cutoff_at_risk": bool(cutoff.get("cutoff_passed")),
            }
        )
    return rows


async def remove_from_queue(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment_id: str,
    user_id: str,
) -> dict[str, Any]:
    payment = await _get_payment(db, account_set_id=account_set_id, payment_id=payment_id)
    if payment.stage not in (STAGE_PREPARE, STAGE_INSTRUCTED):
        raise WorkflowError(
            "Only Prepare or Instructed payments can be removed from the queue.",
            details={"stage": payment.stage},
        )
    await db.execute(
        delete(PaymentStageTransition).where(PaymentStageTransition.payment_id == payment.id)
    )
    await db.delete(payment)
    await write_tenant_audit(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        action="payment.remove_from_queue",
        entity_type="Payment",
        entity_id=payment_id,
        old_value={"stage": payment.stage, "amount": float(payment.amount)},
        new_value={"removed": True},
    )
    return {"payment_id": payment_id, "removed": True}


async def batch_instruct(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment_ids: list[str],
    user_id: str,
    role: str,
) -> dict[str, Any]:
    results = []
    for pid in payment_ids:
        try:
            results.append(
                await instruct_payment(
                    db,
                    account_set_id=account_set_id,
                    payment_id=pid,
                    user_id=user_id,
                    role=role,
                )
            )
        except (WorkflowError, HTTPException) as exc:
            msg = exc.message if isinstance(exc, WorkflowError) else str(exc.detail)
            results.append({"payment_id": pid, "error": msg})
    return {"results": results}


async def batch_pay(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment_ids: list[str],
    user_id: str,
    role: str,
) -> dict[str, Any]:
    results = []
    for pid in payment_ids:
        try:
            results.append(
                await pay_now(
                    db,
                    account_set_id=account_set_id,
                    payment_id=pid,
                    user_id=user_id,
                    role=role,
                )
            )
        except (WorkflowError, HTTPException) as exc:
            msg = exc.message if isinstance(exc, WorkflowError) else str(exc.detail)
            results.append({"payment_id": pid, "error": msg})
    return {"results": results}


async def get_payment_history(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment_id: str,
) -> list[dict[str, Any]]:
    await _get_payment(db, account_set_id=account_set_id, payment_id=payment_id)
    result = await db.execute(
        select(PaymentStageTransition)
        .where(PaymentStageTransition.payment_id == payment_id)
        .order_by(PaymentStageTransition.transitioned_at.asc())
    )
    return [
        {
            "from_stage": t.from_stage,
            "to_stage": t.to_stage,
            "triggered_by": t.triggered_by,
            "reason": t.reason,
            "transitioned_at": t.transitioned_at.isoformat(),
        }
        for t in result.scalars()
    ]


async def confirm_scheduled_payments(db: AsyncSession, *, account_set_id: str) -> dict[str, Any]:
    """Celery beat: confirm Authorised payments with scheduled_date <= today."""
    today = date.today()
    result = await db.execute(
        select(Payment).where(
            Payment.account_set_id == account_set_id,
            Payment.stage == STAGE_AUTHORISED,
            Payment.scheduled_date <= today,
        )
    )
    confirmed = []
    for payment in result.scalars():
        try:
            res = await confirm_payment(
                db,
                account_set_id=account_set_id,
                payment_id=str(payment.id),
                user_id=SYSTEM_TRIGGER,
                role=ROLE_ACCOUNT_SET_ADMIN,
                triggered_by=SYSTEM_TRIGGER,
            )
            confirmed.append(res)
        except WorkflowError as exc:
            confirmed.append({"payment_id": str(payment.id), "error": exc.message})
    return {"confirmed_count": len(confirmed), "results": confirmed}
