"""
Pydantic schemas for fixed asset API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class FixedAssetCreateExtended(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(default="", max_length=128)
    acquisition_date: date
    cost: float = Field(ge=0)
    useful_life_months: int = Field(ge=1)
    depreciation_method: str = Field(
        default="StraightLine", description="StraightLine or DecliningBalance"
    )
    declining_balance_rate: Optional[float] = Field(
        default=None,
        gt=0,
        le=1,
        description="Monthly declining-balance rate (e.g. 0.02 = 2%)",
    )


class AssetRegisterRow(BaseModel):
    id: str
    name: str
    category: str
    acquisition_date: str
    cost: float
    accumulated_depreciation: float
    net_book_value: float
    depreciation_method: str
    is_disposed: bool
    disposed_at: Optional[str] = None


class DepreciationRequest(BaseModel):
    period_code: str = Field(min_length=6, max_length=8)


class DepreciationLinePreview(BaseModel):
    asset_id: str
    name: str
    depreciation_method: str
    depreciation_amount: float
    current_net_book_value: float
    projected_net_book_value: float


class DepreciationPreviewResponse(BaseModel):
    period_code: str
    asset_count: int
    total_depreciation: float
    lines: list[DepreciationLinePreview]


class DepreciationConfirmResponse(BaseModel):
    message: str
    voucher_id: Optional[str] = None
    period_code: Optional[str] = None
    total_depreciation: float
    assets_updated: list[str] = Field(default_factory=list)


class DisposeAssetRequest(BaseModel):
    disposal_date: date
    proceeds_amount: float = Field(ge=0)
    period_code: str = Field(min_length=6, max_length=8)


class DisposeAssetResponse(BaseModel):
    message: str
    asset_id: str
    voucher_id: str
    proceeds_amount: float
    net_book_value_at_disposal: float
    gain_or_loss: float
    is_gain: bool
