"""
Domestic payment initiation service (Task 26).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bank import service as bank_svc
from bank.routing import ROUTING_INTERNAL, ROUTING_SWIFT
from models.bank import BankConnection, RoutingConfig
from models.payment import Payment
from payment import service as payment_svc
from payment import workflow
from payment.routing_matrix import (
    CNY_ONLY_ROUTING,
    SCOPE_DOMESTIC,
    filter_available_routing_methods,
    validate_routing_settlement_pair,
)
from payment.transaction_type_service import (
    ensure_standard_transaction_type,
    get_transaction_type,
)


class DomesticPaymentValidationError(Exception):
    def __init__(self, message: str, *, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


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


async def _assert_routing_configured(
    db: AsyncSession,
    *,
    connection_id: str,
    routing_method: str,
) -> None:
    result = await db.execute(
        select(RoutingConfig).where(
            RoutingConfig.connection_id == connection_id,
            RoutingConfig.routing_method == routing_method,
            RoutingConfig.is_available.is_(True),
        )
    )
    if result.scalar_one_or_none() is None:
        raise DomesticPaymentValidationError(
            f"Routing method '{routing_method}' is not configured or unavailable for this account.",
            details={"routing_method": routing_method},
        )


def _validate_domestic_routing_settlement(
    *,
    routing_method: str,
    settlement_method: str,
    currency: str,
    same_bank: bool | None,
) -> None:
    if routing_method == ROUTING_SWIFT:
        raise DomesticPaymentValidationError(
            "SWIFT is not available for domestic payments.",
            details={"routing_method": routing_method},
        )
    if currency != "CNY" and routing_method in CNY_ONLY_ROUTING:
        raise DomesticPaymentValidationError(
            f"Routing method '{routing_method}' supports CNY only.",
            details={"routing_method": routing_method, "currency": currency},
        )
    if routing_method == ROUTING_INTERNAL and same_bank is False:
        raise DomesticPaymentValidationError(
            "Internal_Transfer requires source and recipient accounts at the same bank.",
            details={"routing_method": routing_method},
        )
    try:
        validate_routing_settlement_pair(
            routing_method,
            settlement_method,
            payment_scope=SCOPE_DOMESTIC,
        )
    except ValueError as exc:
        raise DomesticPaymentValidationError(str(exc)) from exc


async def create_domestic_payment(
    db: AsyncSession,
    *,
    account_set_id: str,
    user_id: str,
    role: str,
    source_connection_id: str,
    recipient_connection_id: str | None,
    recipient_name: str,
    recipient_account: str,
    amount: float,
    currency: str,
    routing_method: str,
    settlement_method: str,
    scheduled_date: date,
    transaction_type_id: str | None = None,
    reference: str | None = None,
) -> dict[str, Any]:
    """
    Create a domestic payment in Prepare status with balance pre-check and cut-off warnings.
    """
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payment amount must be positive.",
        )

    source = await _get_connection(
        db, account_set_id=account_set_id, connection_id=source_connection_id
    )
    same_bank: bool | None = None
    if recipient_connection_id:
        recipient = await _get_connection(
            db, account_set_id=account_set_id, connection_id=recipient_connection_id
        )
        same_bank = source.bank_code.upper() == recipient.bank_code.upper()

    available = filter_available_routing_methods(
        configured_available=await _configured_routing(db, connection_id=source_connection_id),
        bank_code=source.bank_code,
        payment_scope=SCOPE_DOMESTIC,
        currency=currency,
        same_bank=same_bank,
    )
    if routing_method not in available:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_routing_method",
                "message": f"Routing method '{routing_method}' is not available for this domestic payment.",
                "available_routing_methods": sorted(available),
            },
        )

    await _assert_routing_configured(
        db, connection_id=source_connection_id, routing_method=routing_method
    )
    try:
        _validate_domestic_routing_settlement(
            routing_method=routing_method,
            settlement_method=settlement_method,
            currency=currency,
            same_bank=same_bank,
        )
    except DomesticPaymentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_settlement_method", "message": exc.message, **exc.details},
        ) from exc

    balance_info = await bank_svc.get_balance(
        db,
        account_set_id=account_set_id,
        connection_id=source_connection_id,
        allow_stale=True,
    )
    current_balance = float(balance_info.get("current_balance", 0))
    balance_sufficient = current_balance >= amount
    if not balance_sufficient:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "insufficient_balance",
                "message": "Source account balance is insufficient for this payment.",
                "current_balance": current_balance,
                "requested_amount": amount,
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

    payment = Payment(
        id=uuid.uuid4(),
        account_set_id=uuid.UUID(account_set_id),
        connection_id=uuid.UUID(source_connection_id),
        transaction_type_id=txn_type.id,
        payment_scope=SCOPE_DOMESTIC,
        amount=amount,
        currency=currency,
        recipient_name=recipient_name,
        recipient_account=recipient_account,
        routing_method=routing_method,
        settlement_method=settlement_method,
        stage="Prepare",
        scheduled_date=scheduled_date,
        created_by=uuid.UUID(user_id),
    )
    db.add(payment)
    await db.flush()

    cutoff = payment_svc.get_settlement_cutoff_info(
        routing_method=routing_method,
        settlement_method=settlement_method,
    )
    warnings: list[dict[str, Any]] = []
    if cutoff.get("cutoff_passed"):
        warnings.append(
            {
                "code": "cutoff_passed",
                "message": "Settlement cut-off has passed for today; next available settlement date applies.",
                "next_available_date": cutoff.get("next_available_date"),
            }
        )

    result = await workflow.initiate_payment_in_prepare(
        db,
        account_set_id=account_set_id,
        payment=payment,
        txn_type=txn_type,
        user_id=user_id,
        role=role,
        reason=reference or "domestic_payment_created",
    )

    return {
        **result,
        "payment_scope": SCOPE_DOMESTIC,
        "routing_method": routing_method,
        "settlement_method": settlement_method,
        "currency": currency,
        "scheduled_date": scheduled_date.isoformat(),
        "balance_check": {
            "sufficient": balance_sufficient,
            "current_balance": current_balance,
            "stale": balance_info.get("stale", False),
        },
        "cutoff": cutoff,
        "warnings": warnings,
        "reference": reference,
    }


async def _configured_routing(db: AsyncSession, *, connection_id: str) -> set[str]:
    result = await db.execute(
        select(RoutingConfig).where(
            RoutingConfig.connection_id == connection_id,
            RoutingConfig.is_available.is_(True),
        )
    )
    return {c.routing_method for c in result.scalars()}
