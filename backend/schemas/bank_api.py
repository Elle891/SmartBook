"""
Pydantic schemas for Bank Integration API.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


class ConnectBankRequest(BaseModel):
    bank_code: str = Field(min_length=1, max_length=32)
    account_number: str = Field(min_length=1, max_length=64)
    credentials: dict[str, Any]


class ConfigureRoutingRequest(BaseModel):
    routing_method: str = Field(min_length=1, max_length=64)
    params: dict[str, Any]
    is_default: bool = False


class SetDefaultRoutingRequest(BaseModel):
    routing_method: str = Field(min_length=1, max_length=64)


class MarkRoutingUnavailableRequest(BaseModel):
    routing_method: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=512)


class BalanceResponse(BaseModel):
    connection_id: str
    currency: str
    current_balance: Optional[float] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    stale: bool = False
    from_cache: bool = False


class GetBalanceQuery(BaseModel):
    as_of: Optional[date] = None
