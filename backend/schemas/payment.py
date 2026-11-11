"""
Pydantic v2 schemas for Payment, PaymentTransactionType,
PaymentStageTransition, PaymentFieldConfig.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── PaymentTransactionType ────────────────────────────────────────────────────

class PaymentTransactionTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    prepare_mode: str = Field(default="Auto", description="Auto or Manual")
    instruct_mode: str = Field(default="Manual", description="Always Manual")
    check_mode: str = Field(default="Auto", description="Auto or Manual")
    authorise_mode: str = Field(default="Manual", description="Always Manual")
    confirm_mode: str = Field(default="Auto", description="Auto or Manual")
    settle_mode: str = Field(default="Manual", description="Always Manual")


class PaymentTransactionTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    prepare_mode: Optional[str] = None
    check_mode: Optional[str] = None
    confirm_mode: Optional[str] = None
    is_active: Optional[bool] = None


class PaymentTransactionTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    name: str
    prepare_mode: str
    instruct_mode: str
    check_mode: str
    authorise_mode: str
    confirm_mode: str
    settle_mode: str
    is_active: bool
    created_at: datetime


# ── Payment ───────────────────────────────────────────────────────────────────

class PaymentCreate(BaseModel):
    connection_id: uuid.UUID
    transaction_type_id: uuid.UUID
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=8)
    recipient_name: str = Field(min_length=1, max_length=255)
    recipient_account: str = Field(min_length=1, max_length=128)
    routing_method: str = Field(min_length=1, max_length=64)
    settlement_method: str = Field(min_length=1, max_length=64)
    scheduled_date: Optional[date] = None


class PaymentUpdate(BaseModel):
    scheduled_date: Optional[date] = None


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    connection_id: uuid.UUID
    transaction_type_id: uuid.UUID
    amount: float
    currency: str
    recipient_name: str
    recipient_account: str
    routing_method: str
    settlement_method: str
    stage: str
    scheduled_date: Optional[date]
    uetr: Optional[str]
    first_authoriser_id: Optional[uuid.UUID]
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ── PaymentStageTransition ────────────────────────────────────────────────────

class PaymentStageTransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID
    from_stage: str
    to_stage: str
    triggered_by: str
    reason: Optional[str]
    transitioned_at: datetime


# ── PaymentFieldConfig ────────────────────────────────────────────────────────

class PaymentFieldConfigCreate(BaseModel):
    routing_method: str = Field(min_length=1, max_length=64)
    settlement_method: str = Field(min_length=1, max_length=64)
    field_name: str = Field(min_length=1, max_length=128)
    visibility: str = Field(default="Optional", description="Required, Optional, or Hidden")


class PaymentFieldConfigUpdate(BaseModel):
    visibility: str = Field(description="Required, Optional, or Hidden")


class PaymentFieldConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    routing_method: str
    settlement_method: str
    field_name: str
    visibility: str
    updated_at: datetime
