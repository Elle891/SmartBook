"""
Tax Module FastAPI router.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_TAX, require_permission
from platform.db_router import get_tenant_db
from schemas.tax_api import (
    AdjustLineItemRequest,
    FilingHistoryItem,
    FilingReportResponse,
    GenerateFilingRequest,
    SubmitFilingResponse,
)
from tax import service

router = APIRouter(prefix="/account-sets", tags=["tax"])

TenantDB = AsyncSession  # injected via Depends(get_tenant_db)


def _account_set_id_from_user(user: dict[str, Any], path_id: str) -> str:
    jwt_account_set_id = user.get("account_set_id", "")
    if jwt_account_set_id and jwt_account_set_id != path_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_set_id in path does not match the active Account Set in your session.",
        )
    return path_id


@router.post(
    "/{account_set_id}/tax/filings/generate",
    response_model=FilingReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_generate_filing(
    account_set_id: uuid.UUID,
    body: GenerateFilingRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_TAX)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    filing = await service.generate_filing_report(
        db,
        account_set_id=aid,
        period_code=body.period_code,
        tax_type=body.tax_type,
    )
    return filing


@router.get(
    "/{account_set_id}/tax/filings/history",
    response_model=list[FilingHistoryItem],
)
async def api_filing_history(
    account_set_id: uuid.UUID,
    tax_type: str | None = Query(default=None),
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_TAX)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.get_filing_history(
        db, account_set_id=aid, tax_type=tax_type
    )


@router.get("/{account_set_id}/tax/filings/{filing_id}", response_model=FilingReportResponse)
async def api_get_filing(
    account_set_id: uuid.UUID,
    filing_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_TAX)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.get_filing(db, account_set_id=aid, filing_id=str(filing_id))


@router.patch(
    "/{account_set_id}/tax/filings/{filing_id}/line-items",
    response_model=FilingReportResponse,
)
async def api_adjust_line_item(
    account_set_id: uuid.UUID,
    filing_id: uuid.UUID,
    body: AdjustLineItemRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_TAX)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.adjust_line_item(
        db,
        account_set_id=aid,
        filing_id=str(filing_id),
        line_id=body.line_id,
        value=body.value,
    )


@router.post(
    "/{account_set_id}/tax/filings/{filing_id}/submit",
    response_model=SubmitFilingResponse,
)
async def api_submit_filing(
    account_set_id: uuid.UUID,
    filing_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_TAX)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    result = await service.submit_filing(
        db, account_set_id=aid, filing_id=str(filing_id)
    )
    return SubmitFilingResponse(**result)
