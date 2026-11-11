"""
Pydantic schemas for Smart Import API endpoints.
"""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, Field


class ImportUploadResponse(BaseModel):
    session_id: uuid.UUID
    file_name: str
    file_format: str
    total_records: int
    records_skipped: int
    transactions: list["ImportTransactionPreview"]


class ImportTransactionPreview(BaseModel):
    id: uuid.UUID
    txn_date: str
    amount: float
    direction: str
    counterparty: str
    description: str
    reference_number: str
    suggested_debit_account: str
    suggested_credit_account: str
    status: str
    voucher_id: Optional[str] = None


class MappingConfirmItem(BaseModel):
    transaction_id: uuid.UUID
    debit_account: Optional[str] = None
    credit_account: Optional[str] = None
    period_code: Optional[str] = Field(default=None, min_length=6, max_length=8)
    skip: bool = False


class ConfirmMappingRequest(BaseModel):
    mappings: list[MappingConfirmItem] = Field(default_factory=list)


class ImportSummaryResponse(BaseModel):
    session_id: str
    file_name: str
    file_format: str
    status: str
    total_records_processed: int
    vouchers_generated: int
    records_skipped: int


class ConfirmMappingResponse(BaseModel):
    session_id: str
    vouchers_generated: int
    records_skipped: int
    voucher_ids: list[str]
    summary: ImportSummaryResponse
