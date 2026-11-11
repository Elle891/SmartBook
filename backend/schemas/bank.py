"""
Pydantic v2 schemas for BankConnection, BankTransaction, RoutingConfig,
ReconciliationSession, ReconciliationMatch.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── BankConnection ────────────────────────────────────────────────────────────

class BankConnectionCreate(BaseModel):
    bank_code: str = Field(min_length=1, max_length=32)
    account_number: str = Field(min_length=1, max_length=64)
    credentials_vault_path: str = Field(min_length=1, max_length=512)


class BankConnectionUpdate(BaseModel):
    status: Optional[str] = Field(default=None, description="Active or Inactive")


class BankConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    bank_code: str
    account_number: str
    credentials_vault_path: str
    status: str
    last_synced_at: Optional[datetime]
    created_at: datetime


# ── BankTransaction ───────────────────────────────────────────────────────────

class BankTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    connection_id: uuid.UUID
    date: date
    amount: float
    direction: str
    description: str
    reference_number: str
    is_reconciled: bool
    created_at: datetime


# ── RoutingConfig ─────────────────────────────────────────────────────────────

class RoutingConfigCreate(BaseModel):
    routing_method: str = Field(min_length=1, max_length=64)
    params_vault_path: str = Field(min_length=1, max_length=512)
    is_default: bool = False


class RoutingConfigUpdate(BaseModel):
    is_default: Optional[bool] = None
    is_available: Optional[bool] = None


class RoutingConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    routing_method: str
    params_vault_path: str
    is_default: bool
    is_available: bool
    created_at: datetime


# ── ReconciliationSession ─────────────────────────────────────────────────────

class ReconciliationSessionCreate(BaseModel):
    connection_id: uuid.UUID
    period_code: str = Field(min_length=6, max_length=8)


class ReconciliationSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    connection_id: uuid.UUID
    period_code: str
    status: str
    created_at: datetime


# ── ReconciliationMatch ───────────────────────────────────────────────────────

class ReconciliationMatchCreate(BaseModel):
    bank_transaction_id: uuid.UUID
    voucher_entry_id: Optional[uuid.UUID] = None
    match_type: str = Field(description="Exact, Fuzzy, or Manual")


class ReconciliationMatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    bank_transaction_id: uuid.UUID
    voucher_entry_id: Optional[uuid.UUID]
    match_type: str
    matched_at: datetime
