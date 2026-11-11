"""
Pydantic v2 schemas for Voucher, VoucherEntry, VoucherAttachment.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── VoucherEntry ──────────────────────────────────────────────────────────────

class VoucherEntryCreate(BaseModel):
    account_code: str = Field(min_length=1, max_length=32)
    debit_amount: float = Field(default=0.0, ge=0)
    credit_amount: float = Field(default=0.0, ge=0)
    description: str = Field(default="", max_length=512)
    aux_dimension_values: dict[str, Any] = Field(default_factory=dict)
    sequence: int = Field(default=0, ge=0)


class VoucherEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    voucher_id: uuid.UUID
    account_code: str
    debit_amount: float
    credit_amount: float
    description: str
    aux_dimension_values: dict[str, Any]
    sequence: int


# ── VoucherAttachment ─────────────────────────────────────────────────────────

class VoucherAttachmentCreate(BaseModel):
    file_key: str = Field(min_length=1, max_length=512)
    filename: str = Field(min_length=1, max_length=255)


class VoucherAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    voucher_id: uuid.UUID
    file_key: str
    filename: str
    uploaded_at: datetime


# ── Voucher ───────────────────────────────────────────────────────────────────

class VoucherCreate(BaseModel):
    period_code: str = Field(min_length=6, max_length=8)
    type: str = Field(description="Receipt, Payment, or Transfer")
    date: date
    entries: list[VoucherEntryCreate] = Field(min_length=2)
    attachments: list[VoucherAttachmentCreate] = Field(default_factory=list)


class VoucherUpdate(BaseModel):
    date: Optional[date] = None
    entries: Optional[list[VoucherEntryCreate]] = None


class VoucherRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=512)


class VoucherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    period_code: str
    voucher_number: int
    type: str
    date: date
    status: str
    created_by: uuid.UUID
    reviewed_by: Optional[uuid.UUID]
    reviewed_at: Optional[datetime]
    rejection_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    entries: list[VoucherEntryResponse] = []
    attachments: list[VoucherAttachmentResponse] = []


class BatchVoucherRequest(BaseModel):
    voucher_ids: list[uuid.UUID] = Field(min_length=1)


class BatchVoucherResponse(BaseModel):
    succeeded: list[uuid.UUID]
    failed: list[uuid.UUID]
    message: str


class SaveVoucherResponse(BaseModel):
    valid: bool
    voucher_id: str
    message: str
