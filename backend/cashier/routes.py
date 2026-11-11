"""
Cashier module FastAPI router.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_CASHIER, require_permission
from cashier import service
from platform.db_router import get_tenant_db
from schemas.cashier import (
    CashPaymentRequest,
    CashReceiptRequest,
    CashierAccountResponse,
    CashierVoucherResponse,
    FundTransferRequest,
    FxBalanceResponse,
    ReconcileCashRequest,
    ReconciliationReportResponse,
    RegisterCashierAccountRequest,
)

router = APIRouter(prefix="/account-sets", tags=["cashier"])

TenantDB = AsyncSession  # injected via Depends(get_tenant_db)


def _user_id(user: dict[str, Any]) -> str:
    return user.get("user_id") or user.get("sub", "")


def _account_set_id_from_user(user: dict[str, Any], path_id: str) -> str:
    jwt_account_set_id = user.get("account_set_id", "")
    if jwt_account_set_id and jwt_account_set_id != path_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_set_id in path does not match the active Account Set in your session.",
        )
    return path_id


@router.post(
    "/{account_set_id}/cashier/accounts",
    response_model=CashierAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_register_account(
    account_set_id: uuid.UUID,
    body: RegisterCashierAccountRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.register_account(
        db,
        account_set_id=aid,
        account_code=body.account_code,
        cashier_type=body.cashier_type,
        name=body.name,
        currency=body.currency,
        multi_currency_enabled=body.multi_currency_enabled,
    )


@router.post(
    "/{account_set_id}/cashier/receipts",
    response_model=CashierVoucherResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_record_receipt(
    account_set_id: uuid.UUID,
    body: CashReceiptRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    result = await service.record_receipt(
        db,
        account_set_id=aid,
        account_code=body.account_code,
        counterparty_account_code=body.counterparty_account_code,
        amount=body.amount,
        period_code=body.period_code,
        description=body.description,
        user_id=_user_id(user),
        transaction_date=body.transaction_date,
        foreign_amount=body.foreign_amount,
        exchange_rate=body.exchange_rate,
    )
    return CashierVoucherResponse(**result)


@router.post(
    "/{account_set_id}/cashier/payments",
    response_model=CashierVoucherResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_record_payment(
    account_set_id: uuid.UUID,
    body: CashPaymentRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    result = await service.record_payment(
        db,
        account_set_id=aid,
        account_code=body.account_code,
        counterparty_account_code=body.counterparty_account_code,
        amount=body.amount,
        period_code=body.period_code,
        description=body.description,
        user_id=_user_id(user),
        transaction_date=body.transaction_date,
        foreign_amount=body.foreign_amount,
        exchange_rate=body.exchange_rate,
    )
    return CashierVoucherResponse(**result)


@router.post(
    "/{account_set_id}/cashier/transfers",
    response_model=CashierVoucherResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_record_transfer(
    account_set_id: uuid.UUID,
    body: FundTransferRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    result = await service.record_transfer(
        db,
        account_set_id=aid,
        from_account_code=body.from_account_code,
        to_account_code=body.to_account_code,
        income_amount=body.income_amount,
        expenditure_amount=body.expenditure_amount,
        period_code=body.period_code,
        description=body.description,
        user_id=_user_id(user),
        transaction_date=body.transaction_date,
        income_foreign_amount=body.income_foreign_amount,
        income_exchange_rate=body.income_exchange_rate,
        expenditure_foreign_amount=body.expenditure_foreign_amount,
        expenditure_exchange_rate=body.expenditure_exchange_rate,
    )
    return CashierVoucherResponse(**result)


@router.post(
    "/{account_set_id}/cashier/accounts/{account_code}/reconcile",
    response_model=ReconciliationReportResponse,
)
async def api_reconcile_cash(
    account_set_id: uuid.UUID,
    account_code: str,
    body: ReconcileCashRequest,
    period_code: str = Query(..., min_length=6, max_length=8),
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.reconcile_physical_cash(
        db,
        account_set_id=aid,
        account_code=account_code,
        period_code=period_code,
        physical_count=body.physical_count,
    )


@router.get(
    "/{account_set_id}/cashier/accounts/{account_code}/fx-balance",
    response_model=FxBalanceResponse,
)
async def api_fx_balance(
    account_set_id: uuid.UUID,
    account_code: str,
    period_code: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.get_fx_balance(
        db,
        account_set_id=aid,
        account_code=account_code,
        period_code=period_code,
    )
