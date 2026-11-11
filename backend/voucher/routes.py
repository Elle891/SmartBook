"""
Voucher Engine FastAPI router.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_VOUCHERS, require_permission
from platform.db_router import get_tenant_db
from schemas.voucher import (
    BatchVoucherRequest,
    BatchVoucherResponse,
    SaveVoucherResponse,
    VoucherCreate,
    VoucherRejectRequest,
    VoucherResponse,
    VoucherUpdate,
)
from voucher import service

router = APIRouter(prefix="/account-sets", tags=["vouchers"])

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


def _voucher_to_response(voucher: Any) -> dict[str, Any]:
    return {
        "id": voucher.id,
        "account_set_id": voucher.account_set_id,
        "period_code": voucher.period_code,
        "voucher_number": voucher.voucher_number,
        "type": voucher.type,
        "date": voucher.date,
        "status": voucher.status,
        "created_by": voucher.created_by,
        "reviewed_by": voucher.reviewed_by,
        "reviewed_at": voucher.reviewed_at,
        "rejection_reason": voucher.rejection_reason,
        "created_at": voucher.created_at,
        "updated_at": voucher.updated_at,
        "entries": list(getattr(voucher, "entries", []) or []),
        "attachments": list(getattr(voucher, "attachments", []) or []),
    }


@router.post(
    "/{account_set_id}/vouchers",
    response_model=VoucherResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_create_voucher(
    account_set_id: uuid.UUID,
    body: VoucherCreate,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    entries = [e.model_dump() for e in body.entries]
    attachments = [a.model_dump() for a in body.attachments]
    voucher = await service.create_voucher(
        db,
        account_set_id=aid,
        period_code=body.period_code,
        voucher_type=body.type,
        voucher_date=body.date,
        entries=entries,
        attachments=attachments,
        created_by_user_id=_user_id(user),
    )
    loaded = await service.get_voucher(db, account_set_id=aid, voucher_id=str(voucher.id))
    return _voucher_to_response(loaded)


@router.get("/{account_set_id}/vouchers", response_model=list[VoucherResponse])
async def api_list_vouchers(
    account_set_id: uuid.UUID,
    period_code: str | None = None,
    status_filter: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    vouchers = await service.list_vouchers(
        db,
        account_set_id=aid,
        period_code=period_code,
        status_filter=status_filter,
    )
    return [_voucher_to_response(v) for v in vouchers]



@router.get("/{account_set_id}/vouchers/{voucher_id}", response_model=VoucherResponse)
async def api_get_voucher(
    account_set_id: uuid.UUID,
    voucher_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    voucher = await service.get_voucher(db, account_set_id=aid, voucher_id=str(voucher_id))
    return _voucher_to_response(voucher)


@router.put("/{account_set_id}/vouchers/{voucher_id}", response_model=VoucherResponse)
async def api_update_voucher(
    account_set_id: uuid.UUID,
    voucher_id: uuid.UUID,
    body: VoucherUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    entries = [e.model_dump() for e in body.entries] if body.entries is not None else None
    voucher = await service.update_voucher(
        db,
        account_set_id=aid,
        voucher_id=str(voucher_id),
        voucher_date=body.date,
        entries=entries,
    )
    return _voucher_to_response(voucher)


@router.post(
    "/{account_set_id}/vouchers/{voucher_id}/save",
    response_model=SaveVoucherResponse,
)
async def api_save_voucher(
    account_set_id: uuid.UUID,
    voucher_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.save_voucher(db, account_set_id=aid, voucher_id=str(voucher_id))


@router.post(
    "/{account_set_id}/vouchers/{voucher_id}/submit",
    response_model=VoucherResponse,
)
async def api_submit_voucher(
    account_set_id: uuid.UUID,
    voucher_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    voucher = await service.submit_for_review(
        db, account_set_id=aid, voucher_id=str(voucher_id)
    )
    return _voucher_to_response(voucher)


@router.post(
    "/{account_set_id}/vouchers/{voucher_id}/approve",
    response_model=VoucherResponse,
)
async def api_approve_voucher(
    account_set_id: uuid.UUID,
    voucher_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    voucher = await service.approve_voucher(
        db,
        account_set_id=aid,
        voucher_id=str(voucher_id),
        reviewer_id=_user_id(user),
    )
    return _voucher_to_response(voucher)


@router.post(
    "/{account_set_id}/vouchers/{voucher_id}/reject",
    response_model=VoucherResponse,
)
async def api_reject_voucher(
    account_set_id: uuid.UUID,
    voucher_id: uuid.UUID,
    body: VoucherRejectRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    voucher = await service.reject_voucher(
        db,
        account_set_id=aid,
        voucher_id=str(voucher_id),
        reviewer_id=_user_id(user),
        reason=body.reason,
    )
    return _voucher_to_response(voucher)


@router.delete("/{account_set_id}/vouchers/{voucher_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_voucher(
    account_set_id: uuid.UUID,
    voucher_id: uuid.UUID,
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    client_ip = request.client.host if request.client else None
    await service.delete_voucher(
        db,
        account_set_id=aid,
        voucher_id=str(voucher_id),
        user_id=_user_id(user),
        ip_address=client_ip,
    )

