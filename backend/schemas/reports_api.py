"""
Pydantic schemas for Report Engine API.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


class ReportFilterRequest(BaseModel):
    period_code: Optional[str] = Field(default=None, min_length=6, max_length=8)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    report_currency: Optional[str] = Field(default=None, max_length=8)
    entity_id: Optional[str] = None
    entity_group_id: Optional[str] = None
    account_code: Optional[str] = None
    cash_flow_method: Optional[str] = Field(default=None, description="Direct or Indirect")


class ReportResponse(BaseModel):
    report_id: Optional[str] = None
    title: str
    standard: str
    currency: str
    generation_ms: Optional[int] = None
    transaction_count: Optional[int] = None
    data: dict[str, Any] = Field(default_factory=dict)


class DataSourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    connection_mode: str = Field(description="Ledger, API, or DataServer")
    vendor: Optional[str] = None
    endpoint_url: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    credentials: Optional[dict[str, Any]] = None
    config: dict[str, Any] = Field(default_factory=dict)


class DataSourceResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    account_set_id: uuid.UUID
    name: str
    connection_mode: str
    vendor: Optional[str] = None
    endpoint_url: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    status: str


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str


class ReportTemplateCreateRequest(BaseModel):
    data_source_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    layout: dict[str, Any] = Field(default_factory=dict)


class ReportTemplatePublishRequest(BaseModel):
    role_ids: list[str] = Field(default_factory=list)


class ReportTemplateResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    account_set_id: uuid.UUID
    data_source_id: uuid.UUID
    name: str
    layout: dict[str, Any]
    status: str
    published_role_ids: Optional[list] = None
