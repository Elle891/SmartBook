"""
Pydantic schemas for Reconciliation Engine API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class InitiateReconciliationRequest(BaseModel):
    connection_id: str
    period_code: str = Field(min_length=6, max_length=8)


class ManualMatchRequest(BaseModel):
    bank_transaction_id: str
    voucher_entry_id: str


class AutoMatchRequest(BaseModel):
    fuzzy_threshold: int = Field(default=3, ge=0, le=20)
