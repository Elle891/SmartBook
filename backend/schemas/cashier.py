"""
Pydantic schemas for Cashier module endpoints.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RegisterCashierAccountRequest(BaseModel):
    account_code: str = Field(min_length=1, max_length=32)
    cashier_type: str = Field(description="Cash or Bank")
    name: str = Field(min_length=1, max_length=255)
    currency: str = Field(min_length=1, max_length=8)
    multi_currency_enabled: bool = False


class CashierAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    account_code: str
    cashier_type: str
    name: str
    currency: str
    multi_currency_enabled: bool


class CashReceiptRequest(BaseModel):
    account_code: str
    counterparty_account_code: str
    amount: float = Field(gt=0)
    period_code: str = Field(min_length=6, max_length=8)
    description: str = Field(default="", max_length=512)
    transaction_date: Optional[date] = None
    foreign_amount: Optional[float] = Field(default=None, gt=0)
    exchange_rate: Optional[float] = Field(default=None, gt=0)


class CashPaymentRequest(BaseModel):
    account_code: str
    counterparty_account_code: str
    amount: float = Field(gt=0)
    period_code: str = Field(min_length=6, max_length=8)
    description: str = Field(default="", max_length=512)
    transaction_date: Optional[date] = None
    foreign_amount: Optional[float] = Field(default=None, gt=0)
    exchange_rate: Optional[float] = Field(default=None, gt=0)


class FundTransferRequest(BaseModel):
    from_account_code: str
    to_account_code: str
    income_amount: float = Field(gt=0)
    expenditure_amount: float = Field(gt=0)
    period_code: str = Field(min_length=6, max_length=8)
    description: str = Field(default="", max_length=512)
    transaction_date: Optional[date] = None
    income_foreign_amount: Optional[float] = None
    income_exchange_rate: Optional[float] = None
    expenditure_foreign_amount: Optional[float] = None
    expenditure_exchange_rate: Optional[float] = None


class CashierVoucherResponse(BaseModel):
    message: str
    voucher_id: str
    transaction_id: str
    functional_amount: Optional[float] = None
    income_amount: Optional[float] = None
    expenditure_amount: Optional[float] = None


class ReconcileCashRequest(BaseModel):
    physical_count: float = Field(ge=0)


class ReconciliationReportResponse(BaseModel):
    account_code: str
    system_balance: float
    physical_count: float
    discrepancy: float
    is_balanced: bool
    message: str


class FxBalanceResponse(BaseModel):
    account_code: str
    base_currency: str
    currency: str
    multi_currency_enabled: bool
    foreign_currency: Optional[str]
    foreign_balance: float
    functional_balance: float
    effective_exchange_rate: Optional[float]
    period_code: Optional[str] = None
