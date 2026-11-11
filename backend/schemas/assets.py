"""
Pydantic v2 schemas for FixedAsset, IFRSLeaseContract, IFRSRevenueContract,
IFRSPerformanceObligation, IFRSFairValueAdjustment.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── FixedAsset ────────────────────────────────────────────────────────────────

class FixedAssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(default="", max_length=128)
    acquisition_date: date
    cost: float = Field(ge=0)
    useful_life_months: int = Field(ge=1)
    depreciation_method: str = Field(default="StraightLine", description="StraightLine or DecliningBalance")


class FixedAssetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    category: Optional[str] = Field(default=None, max_length=128)
    is_disposed: Optional[bool] = None
    disposed_at: Optional[date] = None


class FixedAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    name: str
    category: str
    acquisition_date: date
    cost: float
    useful_life_months: int
    depreciation_method: str
    declining_balance_rate: Optional[float] = None
    accumulated_depreciation: float
    net_book_value: float
    is_disposed: bool
    disposed_at: Optional[date]
    created_at: datetime


# ── IFRSLeaseContract ─────────────────────────────────────────────────────────

class IFRSLeaseContractCreate(BaseModel):
    asset_id: uuid.UUID
    lease_term_months: int = Field(ge=1)
    lease_liability: float = Field(ge=0)
    rou_asset_value: float = Field(ge=0)
    commencement_date: date


class IFRSLeaseContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    asset_id: uuid.UUID
    lease_term_months: int
    lease_liability: float
    rou_asset_value: float
    commencement_date: date
    created_at: datetime


# ── IFRSRevenueContract ───────────────────────────────────────────────────────

class IFRSRevenueContractCreate(BaseModel):
    contract_reference: str = Field(min_length=1, max_length=128)
    total_value: float = Field(ge=0)


class IFRSRevenueContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    contract_reference: str
    total_value: float
    created_at: datetime


# ── IFRSPerformanceObligation ─────────────────────────────────────────────────

class IFRSPerformanceObligationCreate(BaseModel):
    contract_id: uuid.UUID
    description: str = Field(min_length=1, max_length=512)
    allocated_value: float = Field(ge=0)


class IFRSPerformanceObligationUpdate(BaseModel):
    recognized_to_date: Optional[float] = Field(default=None, ge=0)
    is_satisfied: Optional[bool] = None


class IFRSPerformanceObligationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    description: str
    allocated_value: float
    recognized_to_date: float
    is_satisfied: bool


# ── IFRSFairValueAdjustment ───────────────────────────────────────────────────

class IFRSFairValueAdjustmentCreate(BaseModel):
    account_code: str = Field(min_length=1, max_length=32)
    period_code: str = Field(min_length=6, max_length=8)
    carrying_amount: float
    fair_value: float


class IFRSFairValueAdjustmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    account_code: str
    period_code: str
    carrying_amount: float
    fair_value: float
    adjustment_amount: float
    voucher_id: uuid.UUID
    created_at: datetime
