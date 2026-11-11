"""
Employee, PayrollRun, PayrollLine SQLAlchemy async models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID, JsonType


class Employee(Base):
    """An employee record within an AccountSet."""

    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    department: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    position: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    base_salary: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Employee id={self.id} name={self.name}>"


class PayrollRun(Base):
    """A payroll run for a specific period."""

    __tablename__ = "payroll_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    period_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    # Draft or Confirmed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Draft", index=True)
    voucher_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("vouchers.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<PayrollRun id={self.id} period={self.period_code} status={self.status}>"


class PayrollLine(Base):
    """A single employee's payroll calculation within a PayrollRun."""

    __tablename__ = "payroll_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("payroll_runs.id"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("employees.id"), nullable=False, index=True
    )
    gross_salary: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    # JSON object of deduction_name → amount
    deductions: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    net_salary: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    payslip_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<PayrollLine id={self.id} employee={self.employee_id}>"
