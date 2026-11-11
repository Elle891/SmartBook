"""
IFRS Compliance FastAPI router.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_VOUCHERS, require_permission
from ifrs import service
from platform.db_router import get_tenant_db
from reports.errors import ReportError, StandardMismatchError
from schemas.ifrs_api import (
    FairValueAdjustmentRequest,
    ImpairmentTestRequest,
    RecognizeRevenueRequest,
    RegisterRouAssetRequest,
    ValidateTransactionRequest,
    ValidationResultResponse,
)

router = APIRouter(prefix="/account-sets", tags=["ifrs-compliance"])

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


def _handle_report_error(exc: ReportError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.to_dict())


@router.post("/{account_set_id}/ifrs/fair-value-adjustments")
async def api_fair_value_adjustment(
    account_set_id: uuid.UUID,
    body: FairValueAdjustmentRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.record_fair_value_adjustment(
            db,
            account_set_id=aid,
            account_code=body.account_code,
            period_code=body.period_code,
            carrying_amount=body.carrying_amount,
            fair_value=body.fair_value,
            voucher_date=body.voucher_date,
            user_id=_user_id(user),
        )
    except StandardMismatchError as exc:
        raise _handle_report_error(exc) from exc


@router.post("/{account_set_id}/ifrs/right-of-use-assets")
async def api_register_rou_asset(
    account_set_id: uuid.UUID,
    body: RegisterRouAssetRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.register_right_of_use_asset(
            db,
            account_set_id=aid,
            name=body.name,
            lease_term_months=body.lease_term_months,
            lease_liability=body.lease_liability,
            rou_asset_value=body.rou_asset_value,
            commencement_date=body.commencement_date,
            period_code=body.period_code,
            user_id=_user_id(user),
        )
    except StandardMismatchError as exc:
        raise _handle_report_error(exc) from exc


@router.post("/{account_set_id}/ifrs/revenue-recognition")
async def api_recognize_revenue(
    account_set_id: uuid.UUID,
    body: RecognizeRevenueRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.recognize_revenue(
            db,
            account_set_id=aid,
            obligation_id=body.obligation_id,
            amount=body.amount,
            period_code=body.period_code,
            voucher_date=body.voucher_date,
            user_id=_user_id(user),
        )
    except StandardMismatchError as exc:
        raise _handle_report_error(exc) from exc


@router.post("/{account_set_id}/ifrs/impairment-tests")
async def api_impairment_test(
    account_set_id: uuid.UUID,
    body: ImpairmentTestRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.perform_impairment_test(
            db,
            account_set_id=aid,
            asset_id=body.asset_id,
            recoverable_amount=body.recoverable_amount,
            period_code=body.period_code,
            voucher_date=body.voucher_date,
            user_id=_user_id(user),
        )
    except StandardMismatchError as exc:
        raise _handle_report_error(exc) from exc


@router.post(
    "/{account_set_id}/ifrs/validate-transaction",
    response_model=ValidationResultResponse,
)
async def api_validate_transaction(
    account_set_id: uuid.UUID,
    body: ValidateTransactionRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        result = await service.validate_ifrs_transaction_for_account_set(
            db, account_set_id=aid, entries=body.entries
        )
        return ValidationResultResponse(**result.to_dict())
    except StandardMismatchError as exc:
        raise _handle_report_error(exc) from exc
