"""
Payment Hub workflow API schemas.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class CheckPaymentRequest(BaseModel):
    approved: bool
    rejection_reason: Optional[str] = None


class SettlePaymentRequest(BaseModel):
    settlement_date: date


class BatchPaymentIdsRequest(BaseModel):
    payment_ids: list[str] = Field(min_length=1)


class SchedulePaymentRequest(BaseModel):
    scheduled_date: date


class SaveFieldConfigRequest(BaseModel):
    routing_method: str = Field(min_length=1, max_length=64)
    settlement_method: str = Field(min_length=1, max_length=64)
    field_configs: list[dict[str, str]]


class DefaultSettlementRequest(BaseModel):
    routing_method: str = Field(min_length=1, max_length=64)
    settlement_method: str = Field(min_length=1, max_length=64)


class CreateDomesticPaymentRequest(BaseModel):
    source_connection_id: str
    recipient_connection_id: str | None = None
    recipient_name: str = Field(min_length=1, max_length=255)
    recipient_account: str = Field(min_length=1, max_length=128)
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=8, default="CNY")
    routing_method: str = Field(min_length=1, max_length=64)
    settlement_method: str = Field(min_length=1, max_length=64)
    scheduled_date: date
    transaction_type_id: str | None = None
    reference: str | None = Field(default=None, max_length=512)


class CreateInternationalPaymentRequest(BaseModel):
    source_connection_id: str
    recipient_name: str = Field(min_length=1, max_length=255)
    recipient_account: str = Field(min_length=1, max_length=128)
    beneficiary_bic: str = Field(min_length=8, max_length=11)
    beneficiary_bank_name: str = Field(min_length=1, max_length=255)
    beneficiary_bank_address: str = Field(min_length=1, max_length=512)
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=8)
    settlement_method: str = Field(min_length=1, max_length=64)
    scheduled_date: date
    payment_purpose_code: str = Field(min_length=1, max_length=64)
    remittance_information: str | None = Field(default=None, max_length=512)
    intermediary_bic: str | None = Field(default=None, min_length=8, max_length=11)
    charge_bearer: str | None = Field(default="SLEV", max_length=8)
    end_to_end_id: str | None = Field(default=None, max_length=64)
    transaction_type_id: str | None = None
    reference: str | None = Field(default=None, max_length=512)
