"""
BankConnection, BankTransaction, ReconciliationSession, ReconciliationMatch,
RoutingConfig SQLAlchemy async models.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID, JsonType


class BankConnection(Base):
    """A connection to an external bank account."""

    __tablename__ = "bank_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    bank_code: Mapped[str] = mapped_column(String(32), nullable=False)
    account_number: Mapped[str] = mapped_column(String(64), nullable=False)
    credentials_vault_path: Mapped[str] = mapped_column(String(512), nullable=False)
    # Active or Inactive
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Active", index=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<BankConnection id={self.id} bank={self.bank_code}>"


class BankTransaction(Base):
    """A transaction imported from a bank connection."""

    __tablename__ = "bank_transactions"
    __table_args__ = (
        UniqueConstraint(
            "account_set_id", "date", "amount", "reference_number",
            name="uq_bank_transaction",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("bank_connections.id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    # Inflow or Outflow
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    reference_number: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    is_reconciled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<BankTransaction id={self.id} amount={self.amount}>"


class RoutingConfig(Base):
    """Routing method configuration for a bank connection."""

    __tablename__ = "routing_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("bank_connections.id"), nullable=False, index=True
    )
    routing_method: Mapped[str] = mapped_column(String(64), nullable=False)
    params_vault_path: Mapped[str] = mapped_column(String(512), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<RoutingConfig id={self.id} method={self.routing_method}>"


class ReconciliationSession(Base):
    """A reconciliation session for a period."""

    __tablename__ = "reconciliation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("bank_connections.id"), nullable=False, index=True
    )
    period_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    # InProgress or Completed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="InProgress", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<ReconciliationSession id={self.id} period={self.period_code}>"


class ReconciliationMatch(Base):
    """A match between a bank transaction and a voucher entry."""

    __tablename__ = "reconciliation_matches"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("reconciliation_sessions.id"), nullable=False, index=True
    )
    bank_transaction_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("bank_transactions.id"), nullable=False, index=True
    )
    voucher_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("voucher_entries.id"), nullable=True, index=True
    )
    # Exact, Fuzzy, or Manual
    match_type: Mapped[str] = mapped_column(String(16), nullable=False)
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<ReconciliationMatch id={self.id} type={self.match_type}>"
