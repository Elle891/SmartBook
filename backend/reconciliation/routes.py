"""
Reconciliation Engine FastAPI router.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_CASHIER, require_permission
from platform.db_router import get_tenant_db
from reconciliation import service
from schemas.reconciliation_api import (
    AutoMatchRequest,
    InitiateReconciliationRequest,
    ManualMatchRequest,
)

router = APIRouter(prefix="/account-sets", tags=["reconciliation"])

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
    "/{account_set_id}/reconciliation/sessions",
    status_code=status.HTTP_201_CREATED,
)
async def api_initiate_reconciliation(
    account_set_id: uuid.UUID,
    body: InitiateReconciliationRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.initiate_reconciliation(
        db,
        account_set_id=aid,
        connection_id=body.connection_id,
        period_code=body.period_code,
        user_id=_user_id(user),
    )


@router.post("/{account_set_id}/reconciliation/sessions/{session_id}/auto-match")
async def api_auto_match(
    account_set_id: uuid.UUID,
    session_id: uuid.UUID,
    body: AutoMatchRequest | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    threshold = body.fuzzy_threshold if body else 3
    return await service.auto_match(
        db,
        account_set_id=aid,
        session_id=str(session_id),
        fuzzy_threshold=threshold,
    )


@router.post("/{account_set_id}/reconciliation/sessions/{session_id}/manual-match")
async def api_manual_match(
    account_set_id: uuid.UUID,
    session_id: uuid.UUID,
    body: ManualMatchRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.manual_match(
        db,
        account_set_id=aid,
        session_id=str(session_id),
        bank_transaction_id=body.bank_transaction_id,
        voucher_entry_id=body.voucher_entry_id,
        user_id=_user_id(user),
    )


@router.get("/{account_set_id}/reconciliation/sessions/{session_id}/report")
async def api_reconciliation_report(
    account_set_id: uuid.UUID,
    session_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.get_reconciliation_report(
        db, account_set_id=aid, session_id=str(session_id)
    )


@router.get("/{account_set_id}/reconciliation/sessions/{session_id}/difference")
async def api_reconciliation_difference(
    account_set_id: uuid.UUID,
    session_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.get_difference(
        db, account_set_id=aid, session_id=str(session_id)
    )


@router.post("/{account_set_id}/reconciliation/sessions/{session_id}/complete")
async def api_complete_reconciliation(
    account_set_id: uuid.UUID,
    session_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.complete_reconciliation(
        db,
        account_set_id=aid,
        session_id=str(session_id),
        user_id=_user_id(user),
    )
