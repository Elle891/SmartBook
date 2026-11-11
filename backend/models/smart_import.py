"""
Smart Import session and transaction SQLAlchemy models.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID

SESSION_STATUS_UPLOADED = "Uploaded"
SESSION_STATUS_PARSED = "Parsed"
SESSION_STATUS_CONFIRMED = "Confirmed"

TXN_STATUS_PENDING = "Pending"
TXN_STATUS_SKIPPED_DUPLICATE = "SkippedDuplicate"
TXN_STATUS_CONFIRMED = "Confirmed"
TXN_STATUS_SKIPPED = "Skipped"


class ImportSession(Base):
    """Batch import of bank / payment transaction files."""

    __tablename__ = "import_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_format: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=SESSION_STATUS_UPLOADED)
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vouchers_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ImportTransaction(Base):
    """Parsed transaction row within an import session."""

    __tablename__ = "import_transactions"
    __table_args__ = (
        UniqueConstraint(
            "account_set_id",
            "txn_date",
            "amount",
            "reference_number",
            name="uq_import_txn_dedup",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("import_sessions.id"), nullable=False, index=True
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    txn_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    counterparty: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    reference_number: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    suggested_debit_account: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    suggested_credit_account: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    mapped_debit_account: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    mapped_credit_account: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TXN_STATUS_PENDING)
    voucher_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("vouchers.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
