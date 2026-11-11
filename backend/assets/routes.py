"""
Fixed Asset module FastAPI router.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assets import service
from auth.jwt import get_current_user
from auth.rbac import PERM_ASSETS, require_permission
from models.assets import FixedAsset
from platform.db_router import get_tenant_db
from schemas.assets import FixedAssetResponse
from schemas.assets_api import (
    AssetRegisterRow,
    DepreciationConfirmResponse,
    DepreciationPreviewResponse,
    DepreciationRequest,
    DisposeAssetRequest,
    DisposeAssetResponse,
    FixedAssetCreateExtended,
)

router = APIRouter(prefix="/account-sets", tags=["fixed-assets"])

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
    "/{account_set_id}/assets",
    response_model=FixedAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_register_asset(
    account_set_id: uuid.UUID,
    body: FixedAssetCreateExtended,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_ASSETS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.register_asset(
        db,
        account_set_id=aid,
        name=body.name,
        category=body.category,
        acquisition_date=body.acquisition_date,
        cost=body.cost,
        useful_life_months=body.useful_life_months,
        depreciation_method=body.depreciation_method,
        declining_balance_rate=body.declining_balance_rate,
    )


@router.get("/{account_set_id}/assets/register", response_model=list[AssetRegisterRow])
async def api_asset_register(
    account_set_id: uuid.UUID,
    include_disposed: bool = False,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_ASSETS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.get_asset_register(
        db, account_set_id=aid, include_disposed=include_disposed
    )


@router.get("/{account_set_id}/assets", response_model=list[FixedAssetResponse])
async def api_list_assets(
    account_set_id: uuid.UUID,
    include_disposed: bool = False,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_ASSETS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    stmt = select(FixedAsset).where(FixedAsset.account_set_id == aid)
    if not include_disposed:
        stmt = stmt.where(FixedAsset.is_disposed.is_(False))
    stmt = stmt.order_by(FixedAsset.category, FixedAsset.name)
    assets = list((await db.execute(stmt)).scalars().all())
    return assets


@router.post(
    "/{account_set_id}/assets/depreciation/calculate",
    response_model=DepreciationPreviewResponse,
)
async def api_calculate_depreciation(
    account_set_id: uuid.UUID,
    body: DepreciationRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_ASSETS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.calculate_depreciation(
        db, account_set_id=aid, period_code=body.period_code
    )


@router.post(
    "/{account_set_id}/assets/depreciation/confirm",
    response_model=DepreciationConfirmResponse,
)
async def api_confirm_depreciation(
    account_set_id: uuid.UUID,
    body: DepreciationRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_ASSETS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.confirm_depreciation(
        db,
        account_set_id=aid,
        period_code=body.period_code,
        user_id=_user_id(user),
    )


@router.post(
    "/{account_set_id}/assets/{asset_id}/dispose",
    response_model=DisposeAssetResponse,
)
async def api_dispose_asset(
    account_set_id: uuid.UUID,
    asset_id: uuid.UUID,
    body: DisposeAssetRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_ASSETS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.dispose_asset(
        db,
        account_set_id=aid,
        asset_id=str(asset_id),
        disposal_date=body.disposal_date,
        proceeds_amount=body.proceeds_amount,
        period_code=body.period_code,
        user_id=_user_id(user),
    )
