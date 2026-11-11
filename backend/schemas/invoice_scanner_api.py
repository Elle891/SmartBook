"""
Pydantic schemas for Invoice Scanner API endpoints.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from schemas.reports import InvoiceScanJobResponse


class InvoiceUploadResponse(InvoiceScanJobResponse):
    message: str = "Invoice submitted; OCR processing queued."


class VerifyInvoiceRequest(BaseModel):
    confirmed_data: Optional[dict[str, Any]] = None


class VerificationResponse(BaseModel):
    verified: bool
    reason: str = ""
    verification_status: str


class GenerateVoucherRequest(BaseModel):
    confirmed_data: Optional[dict[str, Any]] = None
    period_code: Optional[str] = Field(default=None, min_length=6, max_length=8)
    expense_account: Optional[str] = None
    tax_account: Optional[str] = None
    payable_account: Optional[str] = None
    allow_unverified: bool = False


class GenerateVoucherResponse(BaseModel):
    job_id: str
    voucher_id: str
    verification_status: str


class AttachmentMetadataResponse(BaseModel):
    file_key: str
    filename: str
    content_type: str
    size_bytes: int
