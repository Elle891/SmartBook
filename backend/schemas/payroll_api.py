"""
Pydantic schemas for payroll endpoints (extends base payroll schemas).
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from schemas.payroll import EmployeeResponse, PayrollLineResponse, PayrollRunResponse


class PayrollSettingsResponse(BaseModel):
    account_set_id: uuid.UUID
    rates: dict[str, float]


class PayrollSettingsUpdate(BaseModel):
    rates: dict[str, float] = Field(
        description="五险一金 contribution rate overrides (fractions of gross salary)"
    )


class PayrollAdjustmentCreate(BaseModel):
    employee_id: uuid.UUID
    period_code: str = Field(min_length=6, max_length=8)
    adjustment_type: str = Field(description="bonus, allowance, deduction, overtime")
    amount: float
    description: str = Field(default="", max_length=512)


class PayrollAdjustmentResponse(BaseModel):
    id: uuid.UUID
    account_set_id: uuid.UUID
    employee_id: uuid.UUID
    period_code: str
    adjustment_type: str
    amount: float
    description: str


class AccruePayrollRequest(BaseModel):
    period_code: str = Field(min_length=6, max_length=8)


class AccruePayrollResponse(BaseModel):
    message: str
    payroll_run_id: str
    voucher_id: str
    period_code: str
    employee_count: int
    total_gross: float
    total_net: float


class PayslipResponse(BaseModel):
    employee_id: str
    employee_name: str
    department: str
    position: str
    period_code: str
    gross_salary: float
    deductions: dict[str, Any]
    employer_contributions: dict[str, float]
    net_salary: float


class DistributePayslipsRequest(BaseModel):
    channel: str = Field(description="email, sms, or wechat")


class DistributePayslipsResponse(BaseModel):
    message: str
    succeeded: list[str]
    failed: list[dict[str, str]]


class EmployeeCreateExtended(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    department: str = Field(default="", max_length=128)
    position: str = Field(default="", max_length=128)
    base_salary: float = Field(ge=0)
    email: Optional[str] = Field(default=None, max_length=255)
    mobile: Optional[str] = Field(default=None, max_length=32)
