"""
InvoiceScanJob, TaxFiling, IFRSLeaseContract, IFRSRevenueContract,
IFRSPerformanceObligation, IFRSFairValueAdjustment SQLAlchemy async models.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID, JsonType


class InvoiceScanJob(Base):
    """An OCR scan job for an invoice image."""

    __tablename__ = "invoice_scan_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    image_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # Pending, Processing, Completed, Failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Pending", index=True)
    extracted_data: Mapped[Optional[dict]] = mapped_column(JsonType, nullable=True)
    verification_result: Mapped[Optional[dict]] = mapped_column(JsonType, nullable=True)
    voucher_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("vouchers.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<InvoiceScanJob id={self.id} status={self.status}>"


class TaxFiling(Base):
    """A tax filing record for VAT or CIT."""

    __tablename__ = "tax_filings"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    period_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    # VAT or CIT
    tax_type: Mapped[str] = mapped_column(String(8), nullable=False)
    # Draft or Submitted
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Draft", index=True)
    report_data: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    confirmation_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<TaxFiling id={self.id} type={self.tax_type} period={self.period_code}>"


class IFRSLeaseContract(Base):
    """IFRS 16 lease contract linked to a right-of-use asset."""

    __tablename__ = "ifrs_lease_contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("fixed_assets.id"), nullable=False, index=True
    )
    lease_term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_liability: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    rou_asset_value: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    commencement_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<IFRSLeaseContract id={self.id}>"


class IFRSRevenueContract(Base):
    """IFRS 15 revenue contract."""

    __tablename__ = "ifrs_revenue_contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    contract_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    total_value: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<IFRSRevenueContract id={self.id} ref={self.contract_reference}>"


class IFRSPerformanceObligation(Base):
    """A performance obligation within an IFRS 15 revenue contract."""

    __tablename__ = "ifrs_performance_obligations"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("ifrs_revenue_contracts.id"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    allocated_value: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    recognized_to_date: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    is_satisfied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<IFRSPerformanceObligation id={self.id}>"


class IFRSFairValueAdjustment(Base):
    """IFRS 9 fair value adjustment record."""

    __tablename__ = "ifrs_fair_value_adjustments"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    account_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    period_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    carrying_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    fair_value: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    adjustment_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("vouchers.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<IFRSFairValueAdjustment id={self.id} account={self.account_code}>"
