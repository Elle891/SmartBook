"""
Smart Import FastAPI router.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_VOUCHERS, require_permission
from platform.db_router import get_tenant_db
from schemas.smart_import_api import (
    ConfirmMappingRequest,
    ConfirmMappingResponse,
    ImportSummaryResponse,
    ImportTransactionPreview,
    ImportUploadResponse,
)
from smart_import import service
from smart_import.parser import FORMAT_AUTO

router = APIRouter(prefix="/account-sets", tags=["smart-import"])

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
    "/{account_set_id}/smart-import/upload",
    response_model=ImportUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_upload_import_file(
    account_set_id: uuid.UUID,
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )
    session = await service.import_file(
        db,
        account_set_id=aid,
        file_name=file.filename or "import.csv",
        content=content,
        file_format=FORMAT_AUTO,
        user_id=_user_id(user),
    )
    transactions = await service.parse_transactions(
        db, session_id=str(session.id), account_set_id=aid
    )
    return ImportUploadResponse(
        session_id=session.id,
        file_name=session.file_name,
        file_format=session.file_format,
        total_records=session.total_records,
        records_skipped=session.records_skipped,
        transactions=[ImportTransactionPreview(**txn) for txn in transactions],
    )


@router.get(
    "/{account_set_id}/smart-import/{session_id}/summary",
    response_model=ImportSummaryResponse,
)
async def api_import_summary(
    account_set_id: uuid.UUID,
    session_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    summary = await service.get_import_summary(
        db, session_id=str(session_id), account_set_id=aid
    )
    return ImportSummaryResponse(**summary)


@router.post(
    "/{account_set_id}/smart-import/{session_id}/confirm",
    response_model=ConfirmMappingResponse,
)
async def api_confirm_mapping(
    account_set_id: uuid.UUID,
    session_id: uuid.UUID,
    body: ConfirmMappingRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_VOUCHERS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    mappings = [item.model_dump() for item in body.mappings]
    result = await service.confirm_mapping(
        db,
        session_id=str(session_id),
        account_set_id=aid,
        user_id=_user_id(user),
        mappings=mappings,
    )
    return ConfirmMappingResponse(**result)
