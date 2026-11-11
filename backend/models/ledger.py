"""
Period, LedgerEntry, AccountBalance SQLAlchemy async models.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID, JsonType


class Period(Base):
    """An accounting month identified by year and month."""

    __tablename__ = "periods"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    # e.g. "202608"
    period_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Period {self.period_code} closed={self.is_closed}>"


class LedgerEntry(Base):
    """A materialized ledger entry derived from an approved voucher entry."""

    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    account_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    period_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("vouchers.id"), nullable=False, index=True
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("voucher_entries.id"), nullable=False, index=True
    )
    debit_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    credit_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    running_balance: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<LedgerEntry id={self.id} account={self.account_code}>"


class AccountBalance(Base):
    """Aggregated balance per account per period."""

    __tablename__ = "account_balances"
    __table_args__ = (
        UniqueConstraint("account_set_id", "account_code", "period_code", name="uq_account_balance"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    account_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    period_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    opening_balance: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    total_debits: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    total_credits: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    closing_balance: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<AccountBalance account={self.account_code} period={self.period_code}>"
