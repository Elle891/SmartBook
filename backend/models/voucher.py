"""
Voucher, VoucherEntry, VoucherAttachment SQLAlchemy async models.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, GUID, JsonType


class Voucher(Base):
    """An accounting voucher recording one or more debit/credit entries."""

    __tablename__ = "vouchers"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    period_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    voucher_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Receipt, Payment, Transfer
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # Draft, PendingReview, Approved, Rejected, Deleted
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Draft", index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        GUID(), nullable=False, index=True
    )
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
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

    entries: Mapped[list["VoucherEntry"]] = relationship(
        "VoucherEntry",
        back_populates="voucher",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    attachments: Mapped[list["VoucherAttachment"]] = relationship(
        "VoucherAttachment",
        back_populates="voucher",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Voucher id={self.id} number={self.voucher_number} status={self.status}>"


class VoucherEntry(Base):
    """A single debit or credit line within a voucher."""

    __tablename__ = "voucher_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("vouchers.id"), nullable=False, index=True
    )
    account_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    debit_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    credit_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    # JSON object of dimension_name → dimension_value
    aux_dimension_values: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    voucher: Mapped["Voucher"] = relationship("Voucher", back_populates="entries")

    def __repr__(self) -> str:
        return f"<VoucherEntry id={self.id} account={self.account_code}>"


class VoucherAttachment(Base):
    """A file attachment linked to a voucher."""

    __tablename__ = "voucher_attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("vouchers.id"), nullable=False, index=True
    )
    file_key: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    voucher: Mapped["Voucher"] = relationship("Voucher", back_populates="attachments")

    def __repr__(self) -> str:
        return f"<VoucherAttachment id={self.id} filename={self.filename}>"
