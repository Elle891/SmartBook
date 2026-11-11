"""
Pydantic v2 schemas for InvoiceScanJob, TaxFiling.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── InvoiceScanJob ────────────────────────────────────────────────────────────

class InvoiceScanJobCreate(BaseModel):
    image_key: str = Field(min_length=1, max_length=512)


class InvoiceScanJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    image_key: str
    status: str
    extracted_data: Optional[dict[str, Any]]
    verification_result: Optional[dict[str, Any]]
    voucher_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


# ── TaxFiling ─────────────────────────────────────────────────────────────────

class TaxFilingCreate(BaseModel):
    period_code: str = Field(min_length=6, max_length=8)
    tax_type: str = Field(description="VAT or CIT")


class TaxFilingUpdate(BaseModel):
    report_data: Optional[dict[str, Any]] = None
    status: Optional[str] = None


class TaxFilingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    period_code: str
    tax_type: str
    status: str
    report_data: dict[str, Any]
    confirmation_number: Optional[str]
    submitted_at: Optional[datetime]
    created_at: datetime
