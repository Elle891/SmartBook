"""
Pydantic v2 schemas for Employee, PayrollRun, PayrollLine.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Employee ──────────────────────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    department: str = Field(default="", max_length=128)
    position: str = Field(default="", max_length=128)
    base_salary: float = Field(ge=0)


class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    department: Optional[str] = Field(default=None, max_length=128)
    position: Optional[str] = Field(default=None, max_length=128)
    base_salary: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    name: str
    department: str
    position: str
    base_salary: float
    email: Optional[str] = None
    mobile: Optional[str] = None
    is_active: bool
    created_at: datetime


# ── PayrollRun ────────────────────────────────────────────────────────────────

class PayrollRunCreate(BaseModel):
    period_code: str = Field(min_length=6, max_length=8)


class PayrollRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_set_id: uuid.UUID
    period_code: str
    status: str
    voucher_id: Optional[uuid.UUID]
    created_at: datetime


# ── PayrollLine ───────────────────────────────────────────────────────────────

class PayrollLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payroll_run_id: uuid.UUID
    employee_id: uuid.UUID
    gross_salary: float
    deductions: dict[str, Any]
    net_salary: float
    payslip_sent: bool
