"""
Period-End Processor FastAPI router.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_PERIOD_END, require_permission
from period_end.accounts import (
    MissingRetainedEarningsAccountError,
    PeriodClosedError,
    UnapprovedVouchersError,
)
from period_end import service
from platform.db_router import get_tenant_db
from schemas.period_end import (
    ClosePeriodResponse,
    OpeningBalanceEntry,
    PeriodEndVoucherResponse,
)

router = APIRouter(prefix="/account-sets", tags=["period-end"])

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


def _map_period_end_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, UnapprovedVouchersError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": str(exc),
                "unapproved_count": exc.count,
            },
        )
    if isinstance(exc, PeriodClosedError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, MissingRetainedEarningsAccountError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    raise exc


@router.post(
    "/{account_set_id}/periods/{period_code}/carry-cost-forward",
    response_model=PeriodEndVoucherResponse,
)
async def api_carry_cost_forward(
    account_set_id: uuid.UUID,
    period_code: str,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PERIOD_END)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.carry_cost_forward(
            db,
            account_set_id=aid,
            period_code=period_code,
            user_id=_user_id(user),
        )
    except (PeriodClosedError, MissingRetainedEarningsAccountError) as exc:
        raise _map_period_end_errors(exc) from exc


@router.post(
    "/{account_set_id}/periods/{period_code}/carry-profit-loss",
    response_model=PeriodEndVoucherResponse,
)
async def api_carry_profit_loss(
    account_set_id: uuid.UUID,
    period_code: str,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PERIOD_END)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.carry_profit_loss(
            db,
            account_set_id=aid,
            period_code=period_code,
            user_id=_user_id(user),
        )
    except (PeriodClosedError, MissingRetainedEarningsAccountError) as exc:
        raise _map_period_end_errors(exc) from exc


@router.post(
    "/{account_set_id}/periods/{period_code}/calculate-depreciation",
    response_model=PeriodEndVoucherResponse,
)
async def api_calculate_depreciation(
    account_set_id: uuid.UUID,
    period_code: str,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PERIOD_END)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.calculate_depreciation(
            db,
            account_set_id=aid,
            period_code=period_code,
            user_id=_user_id(user),
        )
    except PeriodClosedError as exc:
        raise _map_period_end_errors(exc) from exc


@router.get(
    "/{account_set_id}/periods/{period_code}/next-opening-balances",
    response_model=list[OpeningBalanceEntry],
)
async def api_next_opening_balances(
    account_set_id: uuid.UUID,
    period_code: str,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PERIOD_END)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.get_next_period_opening_balances(
        db,
        account_set_id=aid,
        period_code=period_code,
    )


@router.post(
    "/{account_set_id}/periods/{period_code}/close",
    response_model=ClosePeriodResponse,
)
async def api_close_period(
    account_set_id: uuid.UUID,
    period_code: str,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PERIOD_END)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.close_period(
            db,
            account_set_id=aid,
            period_code=period_code,
            user_id=_user_id(user),
        )
    except (UnapprovedVouchersError, PeriodClosedError) as exc:
        raise _map_period_end_errors(exc) from exc
