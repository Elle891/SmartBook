"""ML Forecast FastAPI router (Task 28)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_REPORTS, require_permission
from ml import service as ml_svc
from platform.db_router import get_tenant_db
from schemas.ml_api import ForecastExportRequest

router = APIRouter(prefix="/account-sets", tags=["forecast"])

TenantDB = AsyncSession  # injected via Depends(get_tenant_db)


def _account_set_id_from_user(user: dict[str, Any], path_id: str) -> str:
    jwt_account_set_id = user.get("account_set_id", "")
    if jwt_account_set_id and jwt_account_set_id != path_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_set_id in path does not match the active Account Set in your session.",
        )
    return path_id


@router.get("/{account_set_id}/forecast")
async def api_get_forecast(
    account_set_id: uuid.UUID,
    horizon_months: int = Query(default=6, ge=1, le=12),
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await ml_svc.request_forecast(
        db, account_set_id=aid, horizon_months=horizon_months
    )


@router.get("/{account_set_id}/forecast/metrics")
async def api_forecast_metrics(
    account_set_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await ml_svc.get_model_metrics(db, account_set_id=aid)


@router.get("/{account_set_id}/forecast/comparison")
async def api_forecast_comparison(
    account_set_id: uuid.UUID,
    period: str = Query(..., min_length=6, max_length=8),
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await ml_svc.compare_forecast_vs_actual(
        db, account_set_id=aid, period_code=period
    )


@router.post("/{account_set_id}/forecast/export")
async def api_export_forecast(
    account_set_id: uuid.UUID,
    body: ForecastExportRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    content, media_type, filename = await ml_svc.export_forecast(
        db,
        account_set_id=aid,
        horizon_months=body.horizon_months,
        export_format=body.export_format,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
