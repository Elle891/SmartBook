"""
Pydantic schemas for IFRS Compliance API.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


class FairValueAdjustmentRequest(BaseModel):
    account_code: str = Field(min_length=1, max_length=32)
    period_code: str = Field(min_length=6, max_length=8)
    carrying_amount: float
    fair_value: float
    voucher_date: date


class RegisterRouAssetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    lease_term_months: int = Field(ge=1)
    lease_liability: float = Field(gt=0)
    rou_asset_value: float = Field(gt=0)
    commencement_date: date
    period_code: str = Field(min_length=6, max_length=8)


class RecognizeRevenueRequest(BaseModel):
    obligation_id: str
    amount: float = Field(gt=0)
    period_code: str = Field(min_length=6, max_length=8)
    voucher_date: date


class ImpairmentTestRequest(BaseModel):
    asset_id: str
    recoverable_amount: float = Field(ge=0)
    period_code: str = Field(min_length=6, max_length=8)
    voucher_date: date


class ValidateTransactionRequest(BaseModel):
    entries: list[dict[str, Any]]


class ValidationResultResponse(BaseModel):
    valid: bool
    standard_reference: Optional[str] = None
    message: str = ""
