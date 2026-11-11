"""
Payment Hub core service — status, scheduling, routing options, FX, cut-off.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.bank import BankConnection, RoutingConfig
from models.payment import Payment, PaymentStageTransition
from payment.config import get_dual_auth_threshold
from payment.routing_matrix import (
    SCOPE_DOMESTIC,
    SCOPE_INTERNATIONAL,
    build_routing_settlement_options,
    filter_available_routing_methods,
    settlement_methods_for_routing,
)
from payment.stages import StageModeMap, next_auto_stages
from payment.transaction_type_service import get_transaction_type

_default_settlement: dict[tuple[str, str], str] = {}

_CUTOFF_BY_SETTLEMENT: dict[str, time] = {
    "Real_Time_Gross_Settlement": time(16, 0),
    "Same_Day_Settlement": time(15, 30),
    "Same_Day_Value": time(14, 0),
    "Immediate_Settlement": time(23, 59),
    "Standard_Settlement_T+2": time(15, 0),
    "Express_Settlement_T+1": time(14, 0),
}

_SETTLEMENT_DAY_OFFSET: dict[str, int] = {
    "Standard_Settlement_T+2": 2,
    "Express_Settlement_T+1": 1,
    "Same_Day_Value": 0,
    "Next_Day_Settlement": 1,
    "Two_Day_Settlement": 2,
    "Batch_Settlement_T+1": 1,
}

_STUB_FX_RATES: dict[tuple[str, str], float] = {
    ("CNY", "USD"): 0.138,
    ("USD", "CNY"): 7.25,
    ("CNY", "EUR"): 0.127,
    ("EUR", "CNY"): 7.85,
    ("USD", "EUR"): 0.92,
    ("EUR", "USD"): 1.09,
}


async def _get_connection(
    db: AsyncSession,
    *,
    account_set_id: str,
    connection_id: str,
) -> BankConnection:
    result = await db.execute(
        select(BankConnection).where(
            BankConnection.id == connection_id,
            BankConnection.account_set_id == account_set_id,
        )
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank connection not found.")
    return connection


async def get_payment_status(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment_id: str,
) -> dict[str, Any]:
    result = await db.execute(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.account_set_id == account_set_id,
        )
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")

    history_result = await db.execute(
        select(PaymentStageTransition)
        .where(PaymentStageTransition.payment_id == payment_id)
        .order_by(PaymentStageTransition.transitioned_at.asc())
    )
    history_rows = list(history_result.scalars())

    txn_type = await get_transaction_type(
        db, account_set_id=account_set_id, type_id=str(payment.transaction_type_id)
    )
    threshold = get_dual_auth_threshold(account_set_id)
    modes = StageModeMap.from_transaction_type(txn_type) if txn_type else StageModeMap()
    next_auto = next_auto_stages(modes, from_stage=payment.stage)

    rejection_reason: str | None = None
    for t in reversed(history_rows):
        if t.to_stage == "Prepare" and t.reason:
            rejection_reason = t.reason
            break

    stage_pipeline = [
        {"stage": "Prepare", "mode": modes.prepare_mode},
        {"stage": "Instructed", "mode": modes.instruct_mode},
        {"stage": "Checked", "mode": modes.check_mode},
        {"stage": "Authorised", "mode": modes.authorise_mode},
        {"stage": "Confirmed", "mode": modes.confirm_mode},
        {"stage": "Settled", "mode": modes.settle_mode},
    ]

    return {
        "payment_id": str(payment.id),
        "stage": payment.stage,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "payment_scope": payment.payment_scope,
        "routing_method": payment.routing_method,
        "settlement_method": payment.settlement_method,
        "recipient_name": payment.recipient_name,
        "recipient_account": payment.recipient_account,
        "beneficiary_bic": payment.recipient_agent_bic,
        "beneficiary_bank_name": payment.recipient_agent_name,
        "beneficiary_bank_address": payment.recipient_agent_address,
        "intermediary_bic": payment.intermediary_agent_bic,
        "exchange_rate": float(payment.exchange_rate) if payment.exchange_rate is not None else None,
        "end_to_end_id": payment.end_to_end_id,
        "payment_purpose_code": payment.payment_purpose_code,
        "remittance_info": payment.remittance_info,
        "charge_bearer": payment.charge_bearer,
        "actual_settlement_date": (
            payment.actual_settlement_date.isoformat()
            if payment.actual_settlement_date
            else None
        ),
        "bank_reference": payment.bank_reference,
        "uetr": payment.uetr,
        "scheduled_date": payment.scheduled_date.isoformat() if payment.scheduled_date else None,
        "dual_auth_threshold": threshold,
        "requires_dual_auth": float(payment.amount) >= threshold,
        "first_authoriser_id": (
            str(payment.first_authoriser_id) if payment.first_authoriser_id else None
        ),
        "awaiting_second_authoriser": payment.stage == "PendingSecondAuth",
        "rejection_reason": rejection_reason,
        "transaction_type": (
            {
                "id": str(txn_type.id),
                "name": txn_type.name,
                "prepare_mode": txn_type.prepare_mode,
                "instruct_mode": txn_type.instruct_mode,
                "check_mode": txn_type.check_mode,
                "authorise_mode": txn_type.authorise_mode,
                "confirm_mode": txn_type.confirm_mode,
                "settle_mode": txn_type.settle_mode,
            }
            if txn_type
            else None
        ),
        "stage_pipeline": stage_pipeline,
        "next_auto_stages": next_auto,
        "history": [
            {
                "from_stage": t.from_stage,
                "to_stage": t.to_stage,
                "triggered_by": t.triggered_by,
                "reason": t.reason,
                "transitioned_at": t.transitioned_at.isoformat(),
            }
            for t in history_rows
        ],
    }


async def schedule_payment(
    db: AsyncSession,
    *,
    account_set_id: str,
    payment_id: str,
    scheduled_date: date,
) -> dict[str, Any]:
    result = await db.execute(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.account_set_id == account_set_id,
        )
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")
    if payment.stage != "Prepare":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only Prepare-stage payments can be rescheduled.",
        )
    payment.scheduled_date = scheduled_date
    await db.flush()
    return {
        "payment_id": payment_id,
        "scheduled_date": scheduled_date.isoformat(),
        "stage": payment.stage,
    }


def set_default_settlement_method(
    *,
    account_set_id: str,
    routing_method: str,
    settlement_method: str,
) -> dict[str, str]:
    _default_settlement[(account_set_id, routing_method)] = settlement_method
    return {"routing_method": routing_method, "settlement_method": settlement_method}


def get_default_settlement_method(
    *,
    account_set_id: str,
    routing_method: str,
) -> str | None:
    return _default_settlement.get((account_set_id, routing_method))


def get_settlement_cutoff_info(
    *,
    routing_method: str,
    settlement_method: str,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Return cut-off status for a settlement method (Req 26.8)."""
    today = as_of or date.today()
    now = datetime.now(timezone.utc)
    cutoff = _CUTOFF_BY_SETTLEMENT.get(settlement_method, time(17, 0))
    cutoff_dt = datetime.combine(today, cutoff, tzinfo=timezone.utc)
    passed = now.time() > cutoff
    base_date = today + timedelta(days=1 if passed else 0)
    offset = _SETTLEMENT_DAY_OFFSET.get(settlement_method, 0)
    estimated_date = base_date + timedelta(days=offset)
    return {
        "routing_method": routing_method,
        "settlement_method": settlement_method,
        "cutoff_time": cutoff.isoformat(),
        "cutoff_passed": passed,
        "next_available_date": base_date.isoformat(),
        "estimated_settlement_date": estimated_date.isoformat(),
        "estimated_value_date": estimated_date.isoformat(),
    }


def get_indicative_exchange_rate(
    *,
    source_currency: str,
    target_currency: str,
) -> dict[str, Any]:
    if source_currency == target_currency:
        return {
            "source_currency": source_currency,
            "target_currency": target_currency,
            "rate": 1.0,
            "indicative": True,
        }
    rate = _STUB_FX_RATES.get((source_currency, target_currency))
    if rate is None:
        rate = 1.0
    return {
        "source_currency": source_currency,
        "target_currency": target_currency,
        "rate": rate,
        "indicative": True,
    }


async def get_available_routing_and_settlement(
    db: AsyncSession,
    *,
    account_set_id: str,
    source_connection_id: str,
    recipient_connection_id: str | None,
    payment_scope: str,
    currency: str = "CNY",
) -> dict[str, Any]:
    """
    Filter routing/settlement by scope, configured routes, and availability (Req 25.2–25.3).
    """
    source = await _get_connection(db, account_set_id=account_set_id, connection_id=source_connection_id)

    configured = await db.execute(
        select(RoutingConfig).where(
            RoutingConfig.connection_id == source_connection_id,
            RoutingConfig.is_available.is_(True),
        )
    )
    configured_methods = {c.routing_method for c in configured.scalars()}

    same_bank: bool | None = None
    if recipient_connection_id:
        recipient = await _get_connection(
            db, account_set_id=account_set_id, connection_id=recipient_connection_id
        )
        same_bank = source.bank_code.upper() == recipient.bank_code.upper()

    candidate_routing = filter_available_routing_methods(
        configured_available=configured_methods,
        bank_code=source.bank_code,
        payment_scope=payment_scope,
        currency=currency,
        same_bank=same_bank,
    )

    cutoff_lookup: dict[tuple[str, str], dict] = {}
    for routing in candidate_routing:
        for sm in settlement_methods_for_routing(routing, payment_scope=payment_scope):
            cutoff_lookup[(routing, sm)] = get_settlement_cutoff_info(
                routing_method=routing, settlement_method=sm
            )

    default_lookup = {
        routing: get_default_settlement_method(
            account_set_id=account_set_id, routing_method=routing
        )
        for routing in candidate_routing
    }
    options = build_routing_settlement_options(
        routing_methods=candidate_routing,
        payment_scope=payment_scope,
        default_settlement_lookup=default_lookup,
        cutoff_lookup=cutoff_lookup,
    )

    return {
        "payment_scope": payment_scope,
        "source_connection_id": source_connection_id,
        "recipient_connection_id": recipient_connection_id,
        "currency": currency,
        "options": options,
    }
