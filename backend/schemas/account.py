"""
Pydantic v2 schemas for Chart of Accounts endpoints.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────────────

class CreateAccountRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    account_type: str = Field(description="Asset|Liability|Equity|Revenue|Expense")
    parent_code: Optional[str] = Field(default=None, max_length=32)


class EnableAuxDimensionRequest(BaseModel):
    dimensions: list[str] = Field(
        description="List of dimensions to enable: department, project, customer, supplier, employee"
    )


# ── Response schemas ──────────────────────────────────────────────────────────

class AccountResponse(BaseModel):
    id: str
    account_set_id: str
    code: str
    name: str
    account_type: str
    standard: str
    parent_code: Optional[str]
    level: int
    is_leaf: bool
    is_active: bool
    aux_dimensions: list[str]

    model_config = {"from_attributes": True}


class AccountNode(AccountResponse):
    """Account with nested children for tree response."""
    children: list["AccountNode"] = []

    model_config = {"from_attributes": True}


class AccountTreeResponse(BaseModel):
    account_set_id: str
    accounts: list[AccountNode]


class DeleteAccountResponse(BaseModel):
    message: str


class AuxDimensionResponse(BaseModel):
    code: str
    aux_dimensions: list[str]
    message: str
