"""
Pydantic v2 schemas for AccountSet, AccountSetRole, AccountSetMember.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


ACCOUNT_SET_STATUSES = ("Active", "Closed")


# ── AccountSet ────────────────────────────────────────────────────────────────

class AccountSetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    journal_set_no: str = Field(min_length=1, max_length=64, description="Journal Set No.")
    standard: str = Field(description="CAS or IFRS")
    base_currency: str = Field(min_length=1, max_length=8)
    start_period: str = Field(min_length=6, max_length=8, description="e.g. 202601")
    datasource_type: str = Field(default="Shared", description="Shared or Individual")
    status: str = Field(default="Active", description="Active or Closed")
    datasource_config: Optional[dict[str, Any]] = Field(
        default=None,
        description="Required for Individual datasource: db_host, db_port, db_name, db_user, db_password",
    )

    @field_validator("journal_set_no")
    @classmethod
    def normalize_journal_set_no(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Journal Set No. is required")
        return cleaned

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in ACCOUNT_SET_STATUSES:
            raise ValueError(f"status must be one of {ACCOUNT_SET_STATUSES}")
        return value


class AccountSetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    journal_set_no: Optional[str] = Field(default=None, min_length=1, max_length=64)
    status: Optional[str] = Field(default=None, description="Active or Closed")

    @field_validator("journal_set_no")
    @classmethod
    def normalize_journal_set_no(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Journal Set No. is required")
        return cleaned

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if value not in ACCOUNT_SET_STATUSES:
            raise ValueError(f"status must be one of {ACCOUNT_SET_STATUSES}")
        return value


class AccountSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    journal_set_no: str
    standard: str
    base_currency: str
    start_period: str
    datasource_type: str
    status: str
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ── AccountSetRole ────────────────────────────────────────────────────────────

class AccountSetRoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    permissions: list[str] = Field(default_factory=list)


class AccountSetRoleUpdate(BaseModel):
    permissions: list[str]


class AccountSetRoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    name: str
    is_builtin: bool
    permissions: list[Any]
    created_at: datetime


# ── AccountSetMember ──────────────────────────────────────────────────────────

class AccountSetMemberCreate(BaseModel):
    user_id: uuid.UUID
    role_id: uuid.UUID


class AccountSetMemberUpdate(BaseModel):
    role_id: uuid.UUID


class AccountSetMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    user_id: uuid.UUID
    role_id: uuid.UUID
    joined_at: datetime


# ── Opening Balances ──────────────────────────────────────────────────────────

class OpeningBalanceEntry(BaseModel):
    account_code: str
    debit_amount: float = 0.0
    credit_amount: float = 0.0


class SetOpeningBalancesRequest(BaseModel):
    entries: list[OpeningBalanceEntry]


class SetOpeningBalancesResponse(BaseModel):
    message: str
    total_debits: float
    total_credits: float


# ── Invite User ───────────────────────────────────────────────────────────────

class InviteUserRequest(BaseModel):
    mobile_number: str = Field(min_length=1, max_length=32)
    role_id: uuid.UUID


class DatasourceConfigRequest(BaseModel):
    db_host: str = Field(min_length=1)
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = Field(min_length=1)
    db_user: str = Field(min_length=1)
    db_password: str = Field(min_length=1)
    db_type: str = Field(default="postgresql", description="postgresql or mysql")


class AccountSetMemberDetailResponse(BaseModel):
    id: uuid.UUID
    account_set_id: uuid.UUID
    user_id: uuid.UUID
    role_id: uuid.UUID
    role_name: str
    display_name: str
    mobile: Optional[str] = None
    email: Optional[str] = None
    joined_at: datetime


class SwitchAccountSetResponse(BaseModel):
    account_set_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    access_token: str
    token_type: str = "bearer"


# ── Restore ───────────────────────────────────────────────────────────────────

class RestoreRequest(BaseModel):
    backup_ref: str = Field(min_length=1)
