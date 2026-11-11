"""
Payroll settings, adjustments, and distribution log models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID, JsonType


class PayrollSettings(Base):
    """Per-Account_Set social insurance contribution rates (五险一金)."""

    __tablename__ = "payroll_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, unique=True, index=True
    )
    # Employee + employer rate percentages keyed by contribution type
    rates: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PayrollAdjustment(Base):
    """Period-specific salary adjustment for an employee."""

    __tablename__ = "payroll_adjustments"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("employees.id"), nullable=False, index=True
    )
    period_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    # bonus, allowance, deduction, overtime
    adjustment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class PayslipDistributionLog(Base):
    """Record of payslip delivery attempts (Req 17.8)."""

    __tablename__ = "payslip_distribution_logs"
    __table_args__ = (
        UniqueConstraint(
            "payroll_run_id",
            "employee_id",
            "channel",
            name="uq_payslip_dist_per_channel",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("payroll_runs.id"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("employees.id"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failure_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
