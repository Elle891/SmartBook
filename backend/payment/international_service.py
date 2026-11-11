"""
International (SWIFT) payment initiation service (Task 27).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from bank import service as bank_svc
from bank.routing import ROUTING_SWIFT
from models.payment import Payment
from payment import service as payment_svc
from payment import workflow
from payment.domestic_service import (
    _assert_routing_configured,
    _configured_routing,
    _get_connection,
)
from payment.routing_matrix import (
    SCOPE_INTERNATIONAL,
    filter_available_routing_methods,
    validate_routing_settlement_pair,
)
from payment.swift import SwiftValidationError, validate_bic, validate_charge_bearer
from payment.transaction_type_service import (
    ensure_standard_transaction_type,
    get_transaction_type,
)


class InternationalPaymentValidationError(Exception):
    def __init__(self, message: str, *, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


def _validate_swift_settlement(settlement_method: str) -> None:
    try:
        validate_routing_settlement_pair(
            ROUTING_SWIFT,
            settlement_method,
            payment_scope=SCOPE_INTERNATIONAL,
        )
    except ValueError as exc:
        raise InternationalPaymentValidationError(str(exc)) from exc


def _compute_debit_preview(
    *,
    amount: float,
    payment_currency: str,
    source_currency: str,
) -> dict[str, Any]:
    fx = payment_svc.get_indicative_exchange_rate(
        source_currency=payment_currency,
        target_currency=source_currency,
    )
    rate = float(fx["rate"])
    if payment_currency == source_currency:
        return {
            **fx,
            "estimated_debit_amount": amount,
            "payment_currency": payment_currency,
            "source_currency": source_currency,
        }
    return {
        **fx,
        "estimated_debit_amount": round(amount * rate, 4),
        "payment_currency": payment_currency,
        "source_currency": source_currency,
    }


async def create_international_payment(
    db: AsyncSession,
    *,
    account_set_id: str,
    user_id: str,
    role: str,
    source_connection_id: str,
    recipient_name: str,
    recipient_account: str,
    beneficiary_bic: str,
    beneficiary_bank_name: str,
    beneficiary_bank_address: str,
    amount: float,
    currency: str,
    settlement_method: str,
    scheduled_date: date,
    payment_purpose_code: str,
    remittance_information: str | None = None,
    intermediary_bic: str | None = None,
    charge_bearer: str | None = "SLEV",
    end_to_end_id: str | None = None,
    transaction_type_id: str | None = None,
    reference: str | None = None,
) -> dict[str, Any]:
    """Create an international SWIFT payment in Prepare status."""
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payment amount must be positive.",
        )

    try:
        normalized_bic = validate_bic(beneficiary_bic, field="beneficiary_bic")
        normalized_intermediary = (
            validate_bic(intermediary_bic, field="intermediary_bic")
            if intermediary_bic
            else None
        )
        normalized_charge = validate_charge_bearer(charge_bearer)
    except SwiftValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_swift_field",
                "message": exc.message,
                "field": exc.field,
            },
        ) from exc

    source = await _get_connection(
        db, account_set_id=account_set_id, connection_id=source_connection_id
    )
    available = filter_available_routing_methods(
        configured_available=await _configured_routing(db, connection_id=source_connection_id),
        bank_code=source.bank_code,
        payment_scope=SCOPE_INTERNATIONAL,
        currency=currency,
    )
    if ROUTING_SWIFT not in available:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "swift_unavailable",
                "message": "SWIFT routing is not configured or available for this account.",
                "available_routing_methods": sorted(available),
            },
        )

    await _assert_routing_configured(
        db, connection_id=source_connection_id, routing_method=ROUTING_SWIFT
    )
    try:
        _validate_swift_settlement(settlement_method)
    except InternationalPaymentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_settlement_method", "message": exc.message},
        ) from exc

    balance_info = await bank_svc.get_balance(
        db,
        account_set_id=account_set_id,
        connection_id=source_connection_id,
        allow_stale=True,
    )
    source_currency = str(balance_info.get("currency", "CNY"))
    debit_preview = _compute_debit_preview(
        amount=amount,
        payment_currency=currency,
        source_currency=source_currency,
    )
    estimated_debit = float(debit_preview["estimated_debit_amount"])
    current_balance = float(balance_info.get("current_balance", 0))
    if current_balance < estimated_debit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "insufficient_balance",
                "message": "Source account balance is insufficient for this international payment.",
                "current_balance": current_balance,
                "estimated_debit_amount": estimated_debit,
                "source_currency": source_currency,
            },
        )

    if transaction_type_id:
        txn_type = await get_transaction_type(
            db, account_set_id=account_set_id, type_id=transaction_type_id
        )
        if txn_type is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Payment transaction type not found.",
            )
    else:
        txn_type = await ensure_standard_transaction_type(db, account_set_id=account_set_id)

    e2e_id = end_to_end_id or f"E2E-{uuid.uuid4().hex[:16].upper()}"
    applied_rate = (
        float(debit_preview["rate"]) if currency != source_currency else None
    )

    payment = Payment(
        id=uuid.uuid4(),
        account_set_id=uuid.UUID(account_set_id),
        connection_id=uuid.UUID(source_connection_id),
        transaction_type_id=txn_type.id,
        payment_scope=SCOPE_INTERNATIONAL,
        amount=amount,
        currency=currency,
        recipient_name=recipient_name,
        recipient_account=recipient_account,
        recipient_agent_bic=normalized_bic,
        recipient_agent_name=beneficiary_bank_name,
        recipient_agent_address=beneficiary_bank_address,
        intermediary_agent_bic=normalized_intermediary,
        exchange_rate=applied_rate,
        charge_bearer=normalized_charge,
        payment_purpose_code=payment_purpose_code,
        remittance_info=remittance_information,
        end_to_end_id=e2e_id,
        routing_method=ROUTING_SWIFT,
        settlement_method=settlement_method,
        stage="Prepare",
        scheduled_date=scheduled_date,
        created_by=uuid.UUID(user_id),
    )
    db.add(payment)
    await db.flush()

    cutoff = payment_svc.get_settlement_cutoff_info(
        routing_method=ROUTING_SWIFT,
        settlement_method=settlement_method,
    )
    warnings: list[dict[str, Any]] = []
    if cutoff.get("cutoff_passed"):
        warnings.append(
            {
                "code": "cutoff_passed",
                "message": "SWIFT cut-off has passed; estimated value date adjusted.",
                "next_available_date": cutoff.get("next_available_date"),
                "estimated_settlement_date": cutoff.get("estimated_settlement_date"),
            }
        )

    result = await workflow.initiate_payment_in_prepare(
        db,
        account_set_id=account_set_id,
        payment=payment,
        txn_type=txn_type,
        user_id=user_id,
        role=role,
        reason=reference or "international_payment_created",
    )

    return {
        **result,
        "payment_scope": SCOPE_INTERNATIONAL,
        "routing_method": ROUTING_SWIFT,
        "settlement_method": settlement_method,
        "currency": currency,
        "scheduled_date": scheduled_date.isoformat(),
        "beneficiary_bic": normalized_bic,
        "intermediary_bic": normalized_intermediary,
        "end_to_end_id": e2e_id,
        "exchange_rate": debit_preview,
        "balance_check": {
            "sufficient": True,
            "current_balance": current_balance,
            "estimated_debit_amount": estimated_debit,
            "source_currency": source_currency,
            "stale": balance_info.get("stale", False),
        },
        "cutoff": cutoff,
        "warnings": warnings,
        "reference": reference,
    }
