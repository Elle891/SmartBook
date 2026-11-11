"""ML Forecast API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ForecastExportRequest(BaseModel):
    horizon_months: int = Field(default=6, ge=1, le=12)
    export_format: str = Field(default="csv", pattern="^(?i)(csv|pdf)$")
