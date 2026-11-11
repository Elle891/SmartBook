"""
CashierAccount and CashierTransaction SQLAlchemy models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID


class CashierAccount(Base):
    """Registered cash (1010) or bank (1020) account for cashier operations."""

    __tablename__ = "cashier_accounts"
    __table_args__ = (
        UniqueConstraint("account_set_id", "account_code", name="uq_cashier_account"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    account_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Cash or Bank (Req 16.1 — types 1010 / 1020)
    cashier_type: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    multi_currency_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class CashierTransaction(Base):
    """Cashier operation with optional multi-currency fields (Req 16.6)."""

    __tablename__ = "cashier_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    voucher_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("vouchers.id"), nullable=True, index=True
    )
    # receipt, payment, transfer
    transaction_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    primary_account_code: Mapped[str] = mapped_column(String(32), nullable=False)
    counterparty_account_code: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )
    from_account_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_account_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    period_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    foreign_currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    foreign_amount: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    exchange_rate: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    functional_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    income_amount: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    expenditure_amount: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
