"""
Invoice Scanner FastAPI router.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_INVOICES, require_permission
from invoice_scanner import service
from platform.db_router import get_tenant_db
from schemas.invoice_scanner_api import (
    AttachmentMetadataResponse,
    GenerateVoucherRequest,
    GenerateVoucherResponse,
    InvoiceUploadResponse,
    VerificationResponse,
    VerifyInvoiceRequest,
)
from schemas.reports import InvoiceScanJobResponse

router = APIRouter(prefix="/account-sets", tags=["invoice-scanner"])

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
    "/{account_set_id}/invoices/upload",
    response_model=InvoiceUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_submit_invoice(
    account_set_id: uuid.UUID,
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_INVOICES)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    content = await file.read()
    job = await service.submit_invoice(
        db,
        account_set_id=aid,
        filename=file.filename or "invoice.jpg",
        content=content,
        content_type=file.content_type,
        user_id=_user_id(user),
    )
    return InvoiceUploadResponse.model_validate(job)


@router.get(
    "/{account_set_id}/invoices/{job_id}",
    response_model=InvoiceScanJobResponse,
)
async def api_get_invoice_job(
    account_set_id: uuid.UUID,
    job_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_INVOICES)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.get_scan_job(db, account_set_id=aid, job_id=str(job_id))


@router.post(
    "/{account_set_id}/invoices/{job_id}/verify",
    response_model=VerificationResponse,
)
async def api_verify_invoice(
    account_set_id: uuid.UUID,
    job_id: uuid.UUID,
    body: VerifyInvoiceRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_INVOICES)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    result = await service.verify_invoice(
        db,
        account_set_id=aid,
        job_id=str(job_id),
        confirmed_data=body.confirmed_data,
    )
    return VerificationResponse(**result)


@router.post(
    "/{account_set_id}/invoices/{job_id}/generate-voucher",
    response_model=GenerateVoucherResponse,
)
async def api_generate_voucher(
    account_set_id: uuid.UUID,
    job_id: uuid.UUID,
    body: GenerateVoucherRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_INVOICES)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    result = await service.generate_voucher(
        db,
        account_set_id=aid,
        job_id=str(job_id),
        user_id=_user_id(user),
        confirmed_data=body.confirmed_data,
        period_code=body.period_code,
        expense_account=body.expense_account,
        tax_account=body.tax_account,
        payable_account=body.payable_account,
        allow_unverified=body.allow_unverified,
    )
    return GenerateVoucherResponse(**result)


@router.get(
    "/{account_set_id}/vouchers/{voucher_id}/invoice-attachment",
)
async def api_get_invoice_attachment(
    account_set_id: uuid.UUID,
    voucher_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_INVOICES)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    att = await service.get_attachment(
        db, account_set_id=aid, voucher_id=str(voucher_id)
    )
    return Response(
        content=att["content"],
        media_type=att["content_type"],
        headers={"Content-Disposition": f'inline; filename="{att["filename"]}"'},
    )


@router.get(
    "/{account_set_id}/vouchers/{voucher_id}/invoice-attachment/metadata",
    response_model=AttachmentMetadataResponse,
)
async def api_get_attachment_metadata(
    account_set_id: uuid.UUID,
    voucher_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_INVOICES)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    att = await service.get_attachment(
        db, account_set_id=aid, voucher_id=str(voucher_id)
    )
    return AttachmentMetadataResponse(
        file_key=att["file_key"],
        filename=att["filename"],
        content_type=att["content_type"],
        size_bytes=len(att["content"]),
    )
