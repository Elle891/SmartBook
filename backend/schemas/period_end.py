"""
Pydantic schemas for Period-End Processor endpoints.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class PeriodEndVoucherResponse(BaseModel):
    message: str
    voucher_id: Optional[str] = None
    total_amount: Optional[float] = None
    target_account: Optional[str] = None
    net_profit: Optional[float] = None
    retained_earnings_account: Optional[str] = None
    total_depreciation: Optional[float] = None
    assets: Optional[list[dict[str, Any]]] = None


class OpeningBalanceEntry(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    opening_balance: float


class ClosePeriodResponse(BaseModel):
    message: str
    period_code: str
    next_period_code: str
    accounts_carried: int
    closed_at: Optional[str] = None


class PeriodEndActionRequest(BaseModel):
    voucher_date: Optional[str] = Field(
        default=None,
        description="ISO date for generated voucher (defaults to today)",
    )
