"""
Ledger Engine FastAPI router.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_LEDGER, require_permission
from ledger import service
from platform.db_router import get_tenant_db
from schemas.ledger import (
    AccountSummaryRow,
    GeneralLedgerResponse,
    JournalResponse,
    LedgerEntryResponse,
    SubsidiaryLedgerResponse,
)

router = APIRouter(prefix="/account-sets", tags=["ledger"])

TenantDB = AsyncSession  # injected via Depends(get_tenant_db)


def _account_set_id_from_user(user: dict[str, Any], path_id: str) -> str:
    jwt_account_set_id = user.get("account_set_id", "")
    if jwt_account_set_id and jwt_account_set_id != path_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_set_id in path does not match the active Account Set in your session.",
        )
    return path_id


@router.get(
    "/{account_set_id}/ledger/general",
    response_model=GeneralLedgerResponse,
)
async def api_general_ledger(
    account_set_id: uuid.UUID,
    account_code: str = Query(..., min_length=1),
    period_code: str = Query(..., min_length=6, max_length=8),
    date_from: date | None = None,
    date_to: date | None = None,
    dimension_value: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_LEDGER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    data = await service.get_general_ledger(
        db,
        account_set_id=aid,
        account_code=account_code,
        period_code=period_code,
        date_from=date_from,
        date_to=date_to,
        dimension_value=dimension_value,
    )
    return {
        "account_set_id": uuid.UUID(data["account_set_id"]),
        "account_code": data["account_code"],
        "period_code": data["period_code"],
        "entries": data["entries"],
    }


@router.get(
    "/{account_set_id}/ledger/subsidiary",
    response_model=SubsidiaryLedgerResponse,
)
async def api_subsidiary_ledger(
    account_set_id: uuid.UUID,
    account_code: str = Query(..., min_length=1),
    period_code: str = Query(..., min_length=6, max_length=8),
    dimension: str = Query(..., min_length=1),
    date_from: date | None = None,
    date_to: date | None = None,
    dimension_value: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_LEDGER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.get_subsidiary_ledger(
        db,
        account_set_id=aid,
        account_code=account_code,
        period_code=period_code,
        dimension=dimension,
        date_from=date_from,
        date_to=date_to,
        dimension_value=dimension_value,
    )


@router.get(
    "/{account_set_id}/ledger/cash-journal",
    response_model=JournalResponse,
)
async def api_cash_journal(
    account_set_id: uuid.UUID,
    period_code: str = Query(..., min_length=6, max_length=8),
    date_from: date | None = None,
    date_to: date | None = None,
    account_code: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_LEDGER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.get_cash_journal(
        db,
        account_set_id=aid,
        period_code=period_code,
        date_from=date_from,
        date_to=date_to,
        account_code=account_code,
    )


@router.get(
    "/{account_set_id}/ledger/bank-journal",
    response_model=JournalResponse,
)
async def api_bank_journal(
    account_set_id: uuid.UUID,
    period_code: str = Query(..., min_length=6, max_length=8),
    date_from: date | None = None,
    date_to: date | None = None,
    account_code: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_LEDGER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.get_bank_journal(
        db,
        account_set_id=aid,
        period_code=period_code,
        date_from=date_from,
        date_to=date_to,
        account_code=account_code,
    )


@router.get(
    "/{account_set_id}/ledger/account-summary",
    response_model=list[AccountSummaryRow],
)
async def api_account_summary(
    account_set_id: uuid.UUID,
    period_code: str = Query(..., min_length=6, max_length=8),
    account_code: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_LEDGER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    data = await service.get_account_summary(
        db,
        account_set_id=aid,
        period_code=period_code,
        account_code=account_code,
    )
    return data["rows"]


@router.get("/{account_set_id}/ledger/export")
async def api_export_ledger(
    account_set_id: uuid.UUID,
    period_code: str = Query(..., min_length=6, max_length=8),
    format: str = Query("pdf", alias="format"),
    ledger_type: str = Query("account-summary"),
    account_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_LEDGER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    content, filename, content_type = await service.export_ledger(
        db,
        account_set_id=aid,
        export_format=format,
        ledger_type=ledger_type,
        period_code=period_code,
        account_code=account_code,
        date_from=date_from,
        date_to=date_to,
    )
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
