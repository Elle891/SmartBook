"""
Account Set Manager — FastAPI router.

Endpoints:
  POST   /account-sets
  GET    /account-sets
  POST   /account-sets/{id}/opening-balances
  POST   /account-sets/{id}/switch
  DELETE /account-sets/{id}
  POST   /account-sets/{id}/backup
  POST   /account-sets/{id}/restore
  POST   /account-sets/{id}/reinitialize
  POST   /account-sets/{id}/members
  PATCH  /account-sets/{id}/members/{userId}
  DELETE /account-sets/{id}/members/{userId}
  GET    /account-sets/{id}/roles
  POST   /account-sets/{id}/roles
  PATCH  /account-sets/{id}/roles/{roleId}
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from account_set import service
from auth.jwt import get_current_user, issue_token
from platform.db_router import get_tenant_db
from schemas.account_set import (
    AccountSetCreate,
    AccountSetMemberDetailResponse,
    AccountSetMemberResponse,
    AccountSetMemberUpdate,
    AccountSetResponse,
    AccountSetRoleCreate,
    AccountSetRoleResponse,
    AccountSetRoleUpdate,
    DatasourceConfigRequest,
    InviteUserRequest,
    RestoreRequest,
    SetOpeningBalancesRequest,
    SetOpeningBalancesResponse,
    SwitchAccountSetResponse,
)

router = APIRouter(prefix="/account-sets", tags=["account-sets"])

TenantDB = AsyncSession  # injected via Depends(get_tenant_db)


def _user_id(user: dict[str, Any]) -> str:
    return str(user.get("user_id") or user.get("sub") or "")


# ── Account Set CRUD ──────────────────────────────────────────────────────────


@router.post("", response_model=AccountSetResponse, status_code=status.HTTP_201_CREATED)
async def create_account_set(
    body: AccountSetCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    try:
        account_set = await service.create_account_set(
            db,
            name=body.name,
            journal_set_no=body.journal_set_no,
            standard=body.standard,
            base_currency=body.base_currency,
            start_period=body.start_period,
            datasource_type=body.datasource_type,
            status=body.status,
            datasource_config=getattr(body, "datasource_config", None),
            created_by_user_id=_user_id(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except ConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return account_set


@router.get("", response_model=list[AccountSetResponse])
async def list_account_sets(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    return await service.list_account_sets(db, user_id=_user_id(current_user))


@router.post("/{account_set_id}/opening-balances", response_model=SetOpeningBalancesResponse)
async def set_opening_balances(
    account_set_id: uuid.UUID,
    body: SetOpeningBalancesRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    entries = [e.model_dump() for e in body.entries]
    try:
        result = await service.set_opening_balances(
            db,
            account_set_id=str(account_set_id),
            entries=entries,
            user_id=_user_id(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return result


@router.post("/test-datasource")
async def test_datasource(
    body: DatasourceConfigRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        await service.test_datasource_connection(body.model_dump())
    except ConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"message": "Connection successful"}


@router.post("/{account_set_id}/switch", response_model=SwitchAccountSetResponse)
async def switch_account_set(
    account_set_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    user_id = _user_id(current_user)
    try:
        ctx = await service.switch_account_set(
            db,
            user_id=user_id,
            account_set_id=str(account_set_id),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    token = issue_token(
        user_id=user_id,
        account_set_id=ctx["account_set_id"],
        role=ctx["role"],
        session_id=str(current_user["session_id"]),
    )
    return {
        **ctx,
        "access_token": token,
        "token_type": "bearer",
    }


@router.delete("/{account_set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account_set(
    account_set_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    try:
        await service.delete_account_set(
            db,
            account_set_id=str(account_set_id),
            user_id=_user_id(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{account_set_id}/backup")
async def backup_account_set(
    account_set_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    try:
        result = await service.backup_account_set(
            db,
            account_set_id=str(account_set_id),
            user_id=_user_id(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return result


@router.post("/{account_set_id}/restore")
async def restore_account_set(
    account_set_id: uuid.UUID,
    body: RestoreRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    try:
        result = await service.restore_account_set(
            db,
            account_set_id=str(account_set_id),
            backup_ref=body.backup_ref,
            user_id=_user_id(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return result


@router.post("/{account_set_id}/reinitialize")
async def reinitialize_account_set(
    account_set_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    try:
        result = await service.reinitialize_account_set(
            db,
            account_set_id=str(account_set_id),
            user_id=_user_id(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return result


# ── Member management ─────────────────────────────────────────────────────────


@router.get(
    "/{account_set_id}/members",
    response_model=list[AccountSetMemberDetailResponse],
)
async def list_members(
    account_set_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    try:
        return await service.list_members(
            db,
            account_set_id=str(account_set_id),
            admin_user_id=_user_id(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post(
    "/{account_set_id}/members",
    response_model=AccountSetMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_user(
    account_set_id: uuid.UUID,
    body: InviteUserRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    try:
        member = await service.invite_user(
            db,
            account_set_id=str(account_set_id),
            mobile_number=body.mobile_number,
            role_id=str(body.role_id),
            inviter_user_id=_user_id(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return member


@router.patch("/{account_set_id}/members/{user_id}", response_model=AccountSetMemberResponse)
async def change_user_role(
    account_set_id: uuid.UUID,
    user_id: uuid.UUID,
    body: AccountSetMemberUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    try:
        member = await service.change_user_role(
            db,
            account_set_id=str(account_set_id),
            target_user_id=str(user_id),
            new_role_id=str(body.role_id),
            admin_user_id=_user_id(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return member


@router.delete("/{account_set_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    account_set_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    try:
        await service.remove_user(
            db,
            account_set_id=str(account_set_id),
            target_user_id=str(user_id),
            admin_user_id=_user_id(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ── Role management ───────────────────────────────────────────────────────────


@router.get("/{account_set_id}/roles", response_model=list[AccountSetRoleResponse])
async def list_roles(
    account_set_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    return await service.list_roles(db, account_set_id=str(account_set_id))


@router.post(
    "/{account_set_id}/roles",
    response_model=AccountSetRoleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_role(
    account_set_id: uuid.UUID,
    body: AccountSetRoleCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    try:
        role = await service.create_custom_role(
            db,
            account_set_id=str(account_set_id),
            name=body.name,
            permissions=body.permissions,
            admin_user_id=_user_id(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return role


@router.patch("/{account_set_id}/roles/{role_id}", response_model=AccountSetRoleResponse)
async def update_custom_role(
    account_set_id: uuid.UUID,
    role_id: uuid.UUID,
    body: AccountSetRoleUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: TenantDB = Depends(get_tenant_db),
):
    try:
        role = await service.update_custom_role(
            db,
            account_set_id=str(account_set_id),
            role_id=str(role_id),
            permissions=body.permissions,
            admin_user_id=_user_id(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return role
