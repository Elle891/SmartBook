"""
Chart of Accounts FastAPI router.

Endpoints:
  GET    /account-sets/{account_set_id}/accounts
  POST   /account-sets/{account_set_id}/accounts
  DELETE /account-sets/{account_set_id}/accounts/{code}
  PATCH  /account-sets/{account_set_id}/accounts/{code}/aux-dimensions
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_LEDGER, require_permission
from chart_of_accounts.service import (
    create_account,
    delete_account,
    enable_aux_dimension,
    get_account_tree,
)
from platform.db_router import get_tenant_db
from schemas.account import (
    AccountNode,
    AccountResponse,
    AccountTreeResponse,
    AuxDimensionResponse,
    CreateAccountRequest,
    DeleteAccountResponse,
    EnableAuxDimensionRequest,
)

router = APIRouter(prefix="/account-sets", tags=["chart-of-accounts"])

TenantDB = AsyncSession  # injected via Depends(get_tenant_db)


def _account_set_id_from_user(user: dict[str, Any], path_id: str) -> str:
    """Validate that the path account_set_id matches the JWT claim."""
    jwt_account_set_id = user.get("account_set_id", "")
    if jwt_account_set_id and jwt_account_set_id != path_id:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_set_id in path does not match the active Account Set in your session.",
        )
    return path_id


# ── GET /account-sets/{account_set_id}/accounts ───────────────────────────────

@router.get(
    "/{account_set_id}/accounts",
    response_model=AccountTreeResponse,
    summary="Get Chart of Accounts tree",
)
async def api_get_account_tree(
    account_set_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_LEDGER)),
    db: TenantDB = Depends(get_tenant_db),
) -> dict:
    aid = _account_set_id_from_user(user, account_set_id)
    tree = await get_account_tree(aid, db)
    return {"account_set_id": aid, "accounts": tree}


# ── POST /account-sets/{account_set_id}/accounts ──────────────────────────────

@router.post(
    "/{account_set_id}/accounts",
    response_model=AccountResponse,
    status_code=201,
    summary="Create a new account",
)
async def api_create_account(
    account_set_id: str,
    body: CreateAccountRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_LEDGER)),
    db: TenantDB = Depends(get_tenant_db),
) -> Any:
    aid = _account_set_id_from_user(user, account_set_id)

    from sqlalchemy import select

    from models.account_set import AccountSet

    result = await db.execute(select(AccountSet).where(AccountSet.id == aid))
    account_set = result.scalar_one_or_none()
    standard = account_set.standard if account_set else "CAS"

    account = await create_account(
        account_set_id=aid,
        code=body.code,
        name=body.name,
        account_type=body.account_type,
        standard=standard,
        parent_code=body.parent_code,
        db=db,
    )
    return {
        "id": str(account.id),
        "account_set_id": str(account.account_set_id),
        "code": account.code,
        "name": account.name,
        "account_type": account.account_type,
        "standard": account.standard,
        "parent_code": account.parent_code,
        "level": account.level,
        "is_leaf": account.is_leaf,
        "is_active": account.is_active,
        "aux_dimensions": account.aux_dimensions or [],
    }


# ── DELETE /account-sets/{account_set_id}/accounts/{code} ────────────────────

@router.delete(
    "/{account_set_id}/accounts/{code}",
    response_model=DeleteAccountResponse,
    summary="Delete an account",
)
async def api_delete_account(
    account_set_id: str,
    code: str,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_LEDGER)),
    db: TenantDB = Depends(get_tenant_db),
) -> dict:
    aid = _account_set_id_from_user(user, account_set_id)
    await delete_account(aid, code, db)
    return {"message": f"Account '{code}' deleted successfully."}


# ── PATCH /account-sets/{account_set_id}/accounts/{code}/aux-dimensions ───────

@router.patch(
    "/{account_set_id}/accounts/{code}/aux-dimensions",
    response_model=AuxDimensionResponse,
    summary="Enable auxiliary dimensions on a leaf account",
)
async def api_enable_aux_dimensions(
    account_set_id: str,
    code: str,
    body: EnableAuxDimensionRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_LEDGER)),
    db: TenantDB = Depends(get_tenant_db),
) -> dict:
    aid = _account_set_id_from_user(user, account_set_id)
    account = await enable_aux_dimension(aid, code, body.dimensions, db)
    return {
        "code": account.code,
        "aux_dimensions": account.aux_dimensions,
        "message": f"Auxiliary dimensions updated for account '{code}'.",
    }
