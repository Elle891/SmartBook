"""
Payment Hub workflow FastAPI router.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_CASHIER, PERM_USER_MANAGEMENT, require_permission
from payment import domestic_service as domestic_svc
from payment import international_service as international_svc
from payment import service as payment_svc
from payment import field_config_service as field_svc
from payment import workflow
from payment.stages import WorkflowError
from platform.db_router import get_tenant_db
from schemas.payment import PaymentTransactionTypeCreate, PaymentTransactionTypeUpdate
from schemas.payment_api import (
    BatchPaymentIdsRequest,
    CheckPaymentRequest,
    CreateDomesticPaymentRequest,
    CreateInternationalPaymentRequest,
    DefaultSettlementRequest,
    SaveFieldConfigRequest,
    SchedulePaymentRequest,
    SettlePaymentRequest,
)
from payment import transaction_type_service as txn_type_svc

router = APIRouter(prefix="/account-sets", tags=["payment-hub"])

TenantDB = AsyncSession  # injected via Depends(get_tenant_db)


def _user_id(user: dict[str, Any]) -> str:
    return user.get("user_id") or user.get("sub", "")


def _role(user: dict[str, Any]) -> str:
    return user.get("role", "Viewer")


def _account_set_id_from_user(user: dict[str, Any], path_id: str) -> str:
    jwt_account_set_id = user.get("account_set_id", "")
    if jwt_account_set_id and jwt_account_set_id != path_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_set_id in path does not match the active Account Set in your session.",
        )
    return path_id


def _handle_workflow_error(exc: WorkflowError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.to_dict())


@router.get("/{account_set_id}/payments/queue")
async def api_scheduling_queue(
    account_set_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await workflow.get_scheduling_queue(db, account_set_id=aid)


@router.get("/{account_set_id}/payments/authorised")
async def api_authorised_payments(
    account_set_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await workflow.get_authorised_payments(db, account_set_id=aid)


@router.post("/{account_set_id}/payments/{payment_id}/remove-from-queue")
async def api_remove_from_queue(
    account_set_id: uuid.UUID,
    payment_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await workflow.remove_from_queue(
            db,
            account_set_id=aid,
            payment_id=str(payment_id),
            user_id=_user_id(user),
        )
    except WorkflowError as exc:
        raise _handle_workflow_error(exc) from exc


@router.post("/{account_set_id}/payments/{payment_id}/instruct")
async def api_instruct_payment(
    account_set_id: uuid.UUID,
    payment_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await workflow.instruct_payment(
            db,
            account_set_id=aid,
            payment_id=str(payment_id),
            user_id=_user_id(user),
            role=_role(user),
        )
    except WorkflowError as exc:
        raise _handle_workflow_error(exc) from exc


@router.post("/{account_set_id}/payments/{payment_id}/check")
async def api_check_payment(
    account_set_id: uuid.UUID,
    payment_id: uuid.UUID,
    body: CheckPaymentRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await workflow.check_payment(
            db,
            account_set_id=aid,
            payment_id=str(payment_id),
            approved=body.approved,
            user_id=_user_id(user),
            role=_role(user),
            rejection_reason=body.rejection_reason,
        )
    except WorkflowError as exc:
        raise _handle_workflow_error(exc) from exc


@router.post("/{account_set_id}/payments/{payment_id}/authorise")
async def api_authorise_payment(
    account_set_id: uuid.UUID,
    payment_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await workflow.authorise_payment(
            db,
            account_set_id=aid,
            payment_id=str(payment_id),
            user_id=_user_id(user),
            role=_role(user),
        )
    except WorkflowError as exc:
        raise _handle_workflow_error(exc) from exc


@router.post("/{account_set_id}/payments/{payment_id}/confirm")
async def api_confirm_payment(
    account_set_id: uuid.UUID,
    payment_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await workflow.confirm_payment(
            db,
            account_set_id=aid,
            payment_id=str(payment_id),
            user_id=_user_id(user),
            role=_role(user),
        )
    except WorkflowError as exc:
        raise _handle_workflow_error(exc) from exc


@router.post("/{account_set_id}/payments/{payment_id}/pay-now")
async def api_pay_now(
    account_set_id: uuid.UUID,
    payment_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await workflow.pay_now(
            db,
            account_set_id=aid,
            payment_id=str(payment_id),
            user_id=_user_id(user),
            role=_role(user),
        )
    except WorkflowError as exc:
        raise _handle_workflow_error(exc) from exc


@router.post("/{account_set_id}/payments/{payment_id}/settle")
async def api_settle_payment(
    account_set_id: uuid.UUID,
    payment_id: uuid.UUID,
    body: SettlePaymentRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await workflow.settle_payment(
            db,
            account_set_id=aid,
            payment_id=str(payment_id),
            settlement_date=body.settlement_date,
            user_id=_user_id(user),
            role=_role(user),
        )
    except WorkflowError as exc:
        raise _handle_workflow_error(exc) from exc


@router.get("/{account_set_id}/payments/{payment_id}/history")
async def api_payment_history(
    account_set_id: uuid.UUID,
    payment_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await workflow.get_payment_history(
        db, account_set_id=aid, payment_id=str(payment_id)
    )


@router.post("/{account_set_id}/payments/batch-instruct")
async def api_batch_instruct(
    account_set_id: uuid.UUID,
    body: BatchPaymentIdsRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await workflow.batch_instruct(
        db,
        account_set_id=aid,
        payment_ids=body.payment_ids,
        user_id=_user_id(user),
        role=_role(user),
    )


@router.post("/{account_set_id}/payments/batch-pay")
async def api_batch_pay(
    account_set_id: uuid.UUID,
    body: BatchPaymentIdsRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await workflow.batch_pay(
        db,
        account_set_id=aid,
        payment_ids=body.payment_ids,
        user_id=_user_id(user),
        role=_role(user),
    )


@router.get("/{account_set_id}/payment-transaction-types")
async def api_list_transaction_types(
    account_set_id: uuid.UUID,
    include_inactive: bool = False,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await txn_type_svc.get_transaction_types(
        db, account_set_id=aid, include_inactive=include_inactive
    )


@router.get("/{account_set_id}/payment-transaction-types/default")
async def api_default_transaction_type(
    account_set_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await txn_type_svc.get_default_transaction_type(db, account_set_id=aid)


@router.post(
    "/{account_set_id}/payment-transaction-types",
    status_code=status.HTTP_201_CREATED,
)
async def api_create_transaction_type(
    account_set_id: uuid.UUID,
    body: PaymentTransactionTypeCreate,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_USER_MANAGEMENT)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await txn_type_svc.save_transaction_type(
        db,
        account_set_id=aid,
        user_id=_user_id(user),
        name=body.name,
        prepare_mode=body.prepare_mode,
        instruct_mode=body.instruct_mode,
        check_mode=body.check_mode,
        authorise_mode=body.authorise_mode,
        confirm_mode=body.confirm_mode,
        settle_mode=body.settle_mode,
    )


@router.patch("/{account_set_id}/payment-transaction-types/{type_id}")
async def api_patch_transaction_type(
    account_set_id: uuid.UUID,
    type_id: uuid.UUID,
    body: PaymentTransactionTypeUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_USER_MANAGEMENT)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await txn_type_svc.update_transaction_type(
        db,
        account_set_id=aid,
        type_id=str(type_id),
        user_id=_user_id(user),
        name=body.name,
        prepare_mode=body.prepare_mode,
        check_mode=body.check_mode,
        confirm_mode=body.confirm_mode,
        is_active=body.is_active,
    )


@router.post(
    "/{account_set_id}/payments/domestic",
    status_code=status.HTTP_201_CREATED,
)
async def api_create_domestic_payment(
    account_set_id: uuid.UUID,
    body: CreateDomesticPaymentRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await domestic_svc.create_domestic_payment(
        db,
        account_set_id=aid,
        user_id=_user_id(user),
        role=_role(user),
        source_connection_id=body.source_connection_id,
        recipient_connection_id=body.recipient_connection_id,
        recipient_name=body.recipient_name,
        recipient_account=body.recipient_account,
        amount=body.amount,
        currency=body.currency,
        routing_method=body.routing_method,
        settlement_method=body.settlement_method,
        scheduled_date=body.scheduled_date,
        transaction_type_id=body.transaction_type_id,
        reference=body.reference,
    )


@router.post(
    "/{account_set_id}/payments/international",
    status_code=status.HTTP_201_CREATED,
)
async def api_create_international_payment(
    account_set_id: uuid.UUID,
    body: CreateInternationalPaymentRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await international_svc.create_international_payment(
        db,
        account_set_id=aid,
        user_id=_user_id(user),
        role=_role(user),
        source_connection_id=body.source_connection_id,
        recipient_name=body.recipient_name,
        recipient_account=body.recipient_account,
        beneficiary_bic=body.beneficiary_bic,
        beneficiary_bank_name=body.beneficiary_bank_name,
        beneficiary_bank_address=body.beneficiary_bank_address,
        amount=body.amount,
        currency=body.currency,
        settlement_method=body.settlement_method,
        scheduled_date=body.scheduled_date,
        payment_purpose_code=body.payment_purpose_code,
        remittance_information=body.remittance_information,
        intermediary_bic=body.intermediary_bic,
        charge_bearer=body.charge_bearer,
        end_to_end_id=body.end_to_end_id,
        transaction_type_id=body.transaction_type_id,
        reference=body.reference,
    )


@router.get("/{account_set_id}/payments/{payment_id}/status")
async def api_payment_status(
    account_set_id: uuid.UUID,
    payment_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await payment_svc.get_payment_status(
        db, account_set_id=aid, payment_id=str(payment_id)
    )


@router.post("/{account_set_id}/payments/{payment_id}/schedule")
async def api_schedule_payment(
    account_set_id: uuid.UUID,
    payment_id: uuid.UUID,
    body: SchedulePaymentRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await payment_svc.schedule_payment(
        db,
        account_set_id=aid,
        payment_id=str(payment_id),
        scheduled_date=body.scheduled_date,
    )


@router.get("/{account_set_id}/payments/routing-options")
async def api_routing_and_settlement(
    account_set_id: uuid.UUID,
    source_connection_id: uuid.UUID = Query(...),
    recipient_connection_id: uuid.UUID | None = Query(default=None),
    payment_scope: str = Query(default="Domestic"),
    currency: str = Query(default="CNY"),
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await payment_svc.get_available_routing_and_settlement(
        db,
        account_set_id=aid,
        source_connection_id=str(source_connection_id),
        recipient_connection_id=str(recipient_connection_id) if recipient_connection_id else None,
        payment_scope=payment_scope,
        currency=currency,
    )


@router.post("/{account_set_id}/payments/default-settlement-method")
async def api_set_default_settlement(
    account_set_id: uuid.UUID,
    body: DefaultSettlementRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    _account_set_id_from_user(user, str(account_set_id))
    return payment_svc.set_default_settlement_method(
        account_set_id=str(account_set_id),
        routing_method=body.routing_method,
        settlement_method=body.settlement_method,
    )


@router.get("/{account_set_id}/payments/settlement-cutoff")
async def api_settlement_cutoff(
    account_set_id: uuid.UUID,
    routing_method: str = Query(...),
    settlement_method: str = Query(...),
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    _account_set_id_from_user(user, str(account_set_id))
    return payment_svc.get_settlement_cutoff_info(
        routing_method=routing_method,
        settlement_method=settlement_method,
    )


@router.get("/{account_set_id}/payments/exchange-rate")
async def api_exchange_rate(
    account_set_id: uuid.UUID,
    source_currency: str = Query(...),
    target_currency: str = Query(...),
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    _account_set_id_from_user(user, str(account_set_id))
    return payment_svc.get_indicative_exchange_rate(
        source_currency=source_currency,
        target_currency=target_currency,
    )


@router.get("/{account_set_id}/payment-field-config")
async def api_get_field_config(
    account_set_id: uuid.UUID,
    routing_method: str = Query(...),
    settlement_method: str = Query(...),
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await field_svc.get_field_configuration(
        db,
        account_set_id=aid,
        routing_method=routing_method,
        settlement_method=settlement_method,
    )


@router.post("/{account_set_id}/payment-field-config")
async def api_save_field_config(
    account_set_id: uuid.UUID,
    body: SaveFieldConfigRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_USER_MANAGEMENT)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await field_svc.save_field_configuration(
        db,
        account_set_id=aid,
        routing_method=body.routing_method,
        settlement_method=body.settlement_method,
        field_configs=body.field_configs,
        user_id=_user_id(user),
    )
