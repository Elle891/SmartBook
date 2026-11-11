"""
Pydantic v2 schemas for Period, LedgerEntry, AccountBalance.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Period ────────────────────────────────────────────────────────────────────

class PeriodCreate(BaseModel):
    period_code: str = Field(min_length=6, max_length=8)
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class PeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    period_code: str
    year: int
    month: int
    is_closed: bool
    closed_at: Optional[datetime]
    created_at: datetime


# ── LedgerEntry ───────────────────────────────────────────────────────────────

class LedgerEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    account_code: str
    period_code: str
    voucher_id: uuid.UUID
    entry_id: uuid.UUID
    debit_amount: float
    credit_amount: float
    running_balance: float
    entry_date: date
    created_at: datetime


# ── AccountBalance ────────────────────────────────────────────────────────────

class AccountBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    account_code: str
    period_code: str
    opening_balance: float
    total_debits: float
    total_credits: float
    closing_balance: float
    updated_at: datetime


# ── Query params ──────────────────────────────────────────────────────────────

class LedgerQueryParams(BaseModel):
    account_code: Optional[str] = None
    period_code: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    dimension_value: Optional[str] = None


class ExportLedgerRequest(BaseModel):
    format: str = Field(default="pdf", description="pdf or excel")
    account_code: Optional[str] = None
    period_code: Optional[str] = None


class GeneralLedgerResponse(BaseModel):
    account_set_id: uuid.UUID
    account_code: str
    period_code: str
    entries: list[LedgerEntryResponse]


class SubsidiaryLedgerGroup(BaseModel):
    dimension: str
    dimension_value: str
    entries: list[dict[str, Any]]


class SubsidiaryLedgerResponse(BaseModel):
    account_set_id: str
    account_code: str
    period_code: str
    dimension: str
    groups: list[SubsidiaryLedgerGroup]


class JournalEntryItem(BaseModel):
    entry_date: date
    voucher_number: int
    voucher_type: str
    account_code: str
    account_name: str
    description: str
    debit_amount: float
    credit_amount: float
    running_balance: float


class JournalResponse(BaseModel):
    account_set_id: str
    period_code: str
    journal_type: str
    entries: list[JournalEntryItem]


class AccountSummaryRow(BaseModel):
    account_code: str
    account_name: str
    opening_balance: float
    total_debits: float
    total_credits: float
    closing_balance: float
