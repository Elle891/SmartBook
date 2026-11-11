"""
Bank Integration FastAPI router.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_CASHIER, require_permission
from bank import service
from bank.errors import BankConnectionError, BankError
from platform.db_router import get_tenant_db
from schemas.bank_api import (
    ConfigureRoutingRequest,
    ConnectBankRequest,
    MarkRoutingUnavailableRequest,
    SetDefaultRoutingRequest,
)

router = APIRouter(prefix="/account-sets", tags=["bank-integration"])

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


def _handle_bank_error(exc: BankError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.to_dict())


@router.get("/{account_set_id}/bank/connections")
async def api_list_connections(
    account_set_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.list_connections(db, account_set_id=aid)


@router.post("/{account_set_id}/bank/connections", status_code=status.HTTP_201_CREATED)
async def api_connect_bank(
    account_set_id: uuid.UUID,
    body: ConnectBankRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.connect_bank(
            db,
            account_set_id=aid,
            bank_code=body.bank_code,
            account_number=body.account_number,
            credentials=body.credentials,
            user_id=_user_id(user),
        )
    except BankConnectionError as exc:
        raise _handle_bank_error(exc) from exc


@router.post("/{account_set_id}/bank/connections/{connection_id}/verify")
async def api_verify_connection(
    account_set_id: uuid.UUID,
    connection_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.verify_connection(
            db, account_set_id=aid, connection_id=str(connection_id)
        )
    except BankConnectionError as exc:
        raise _handle_bank_error(exc) from exc


@router.post("/{account_set_id}/bank/connections/{connection_id}/sync")
async def api_sync_transactions(
    account_set_id: uuid.UUID,
    connection_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.sync_transactions(
            db,
            account_set_id=aid,
            connection_id=str(connection_id),
            user_id=_user_id(user),
        )
    except BankConnectionError as exc:
        raise _handle_bank_error(exc) from exc


@router.get("/{account_set_id}/bank/connections/{connection_id}/balance")
async def api_get_balance(
    account_set_id: uuid.UUID,
    connection_id: uuid.UUID,
    as_of: date | None = Query(default=None),
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.get_balance(
            db,
            account_set_id=aid,
            connection_id=str(connection_id),
            as_of=as_of,
        )
    except BankConnectionError as exc:
        raise _handle_bank_error(exc) from exc


@router.post("/{account_set_id}/bank/connections/{connection_id}/routing")
async def api_configure_routing(
    account_set_id: uuid.UUID,
    connection_id: uuid.UUID,
    body: ConfigureRoutingRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.configure_routing_method(
        db,
        account_set_id=aid,
        connection_id=str(connection_id),
        routing_method=body.routing_method,
        params=body.params,
        is_default=body.is_default,
        user_id=_user_id(user),
    )


@router.get("/{account_set_id}/bank/connections/{connection_id}/routing/available")
async def api_available_routing(
    account_set_id: uuid.UUID,
    connection_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.get_available_routing_methods(
        db, account_set_id=aid, connection_id=str(connection_id)
    )


@router.get("/{account_set_id}/bank/connections/{connection_id}/routing")
async def api_get_routing_config(
    account_set_id: uuid.UUID,
    connection_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.get_routing_config(
        db, account_set_id=aid, connection_id=str(connection_id)
    )


@router.post("/{account_set_id}/bank/connections/{connection_id}/routing/default")
async def api_set_default_routing(
    account_set_id: uuid.UUID,
    connection_id: uuid.UUID,
    body: SetDefaultRoutingRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.set_default_routing_method(
        db,
        account_set_id=aid,
        connection_id=str(connection_id),
        routing_method=body.routing_method,
        user_id=_user_id(user),
    )


@router.post("/{account_set_id}/bank/connections/{connection_id}/routing/unavailable")
async def api_mark_routing_unavailable(
    account_set_id: uuid.UUID,
    connection_id: uuid.UUID,
    body: MarkRoutingUnavailableRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_CASHIER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.mark_routing_method_unavailable(
        db,
        account_set_id=aid,
        connection_id=str(connection_id),
        routing_method=body.routing_method,
        reason=body.reason,
        user_id=_user_id(user),
    )
