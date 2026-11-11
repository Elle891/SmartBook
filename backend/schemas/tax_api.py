"""
Pydantic schemas for Tax Module API.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class GenerateFilingRequest(BaseModel):
    period_code: str = Field(min_length=6, max_length=8)
    tax_type: str = Field(description="VAT or CIT")


class AdjustLineItemRequest(BaseModel):
    line_id: str = Field(min_length=1, max_length=64)
    value: float


class FilingLineItem(BaseModel):
    line_id: str
    label: str
    amount: float
    editable: bool = True
    adjusted: bool = False


class FilingReportResponse(BaseModel):
    id: uuid.UUID
    account_set_id: uuid.UUID
    period_code: str
    tax_type: str
    status: str
    report_data: dict[str, Any]
    confirmation_number: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime


class SubmitFilingResponse(BaseModel):
    filing_id: str
    success: bool
    status: str
    confirmation_number: Optional[str] = None
    submitted_at: Optional[str] = None
    message: str
    report_data_preserved: bool = True


class FilingHistoryItem(BaseModel):
    id: str
    period_code: str
    tax_type: str
    status: str
    confirmation_number: Optional[str] = None
    submitted_at: Optional[str] = None
    created_at: str
