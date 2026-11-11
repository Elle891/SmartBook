"""
Pydantic v2 schemas for ForecastModel, ForecastResult, ForecastPeriod, ForecastSnapshot.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── ForecastModel ─────────────────────────────────────────────────────────────

class ForecastModelCreate(BaseModel):
    model_type: str = Field(min_length=1, max_length=64)
    artifact_path: str = Field(min_length=1, max_length=512)
    trained_at: datetime
    mape: float = Field(ge=0)
    rmse: float = Field(ge=0)


class ForecastModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    model_type: str
    artifact_path: str
    trained_at: datetime
    mape: float
    rmse: float
    is_active: bool


# ── ForecastResult ────────────────────────────────────────────────────────────

class ForecastResultCreate(BaseModel):
    model_id: uuid.UUID
    generated_at: datetime
    horizon_months: int = Field(ge=1, le=60)


class ForecastResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    model_id: uuid.UUID
    generated_at: datetime
    horizon_months: int


# ── ForecastPeriod ────────────────────────────────────────────────────────────

class ForecastPeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    result_id: uuid.UUID
    period_code: str
    predicted_inflow: float
    predicted_outflow: float
    confidence_lower: float
    confidence_upper: float


# ── ForecastSnapshot ──────────────────────────────────────────────────────────

class ForecastSnapshotCreate(BaseModel):
    result_id: uuid.UUID
    snapshot_at: datetime
    notes: Optional[str] = Field(default=None, max_length=512)


class ForecastSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    result_id: uuid.UUID
    snapshot_at: datetime
    notes: Optional[str]
