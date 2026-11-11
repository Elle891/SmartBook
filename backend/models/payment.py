"""
Payment, PaymentTransactionType, PaymentStageTransition, PaymentFieldConfig
SQLAlchemy async models.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID, JsonType


class PaymentTransactionType(Base):
    """Configuration for each stage mode (Auto/Manual) per payment type."""

    __tablename__ = "payment_transaction_types"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # Each stage mode: Auto or Manual
    prepare_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="Auto")
    instruct_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="Manual")
    check_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="Auto")
    authorise_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="Manual")
    confirm_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="Auto")
    settle_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="Manual")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<PaymentTransactionType id={self.id} name={self.name}>"


class Payment(Base):
    """A payment instruction in the settlement workflow."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("bank_connections.id"), nullable=False, index=True
    )
    transaction_type_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("payment_transaction_types.id"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_account: Mapped[str] = mapped_column(String(128), nullable=False)
    recipient_agent_bic: Mapped[Optional[str]] = mapped_column(String(11), nullable=True)
    recipient_agent_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recipient_agent_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intermediary_agent_bic: Mapped[Optional[str]] = mapped_column(String(11), nullable=True)
    exchange_rate: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    charge_bearer: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    payment_purpose_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    remittance_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    end_to_end_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    routing_method: Mapped[str] = mapped_column(String(64), nullable=False)
    settlement_method: Mapped[str] = mapped_column(String(64), nullable=False)
    # Domestic or International
    payment_scope: Mapped[str] = mapped_column(String(16), nullable=False, default="Domestic")
    # Prepare, Instructed, Checked, Authorised, PendingSecondAuth, Confirmed, Settled
    stage: Mapped[str] = mapped_column(String(24), nullable=False, default="Prepare", index=True)
    scheduled_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    actual_settlement_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    uetr: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    bank_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    iso_pain001: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    first_authoriser_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        GUID(), nullable=False, index=True
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
        return f"<Payment id={self.id} stage={self.stage} amount={self.amount}>"


class PaymentStageTransition(Base):
    """Audit trail of every stage change for a payment."""

    __tablename__ = "payment_stage_transitions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("payments.id"), nullable=False, index=True
    )
    from_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    to_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    # user_id or "system"
    triggered_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    transitioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<PaymentStageTransition {self.from_stage}→{self.to_stage}>"


class PaymentFieldConfig(Base):
    """Per-AccountSet field visibility config for ISO 20022 payment fields."""

    __tablename__ = "payment_field_configs"
    __table_args__ = (
        UniqueConstraint(
            "account_set_id", "routing_method", "settlement_method", "field_name",
            name="uq_payment_field_config",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    routing_method: Mapped[str] = mapped_column(String(64), nullable=False)
    settlement_method: Mapped[str] = mapped_column(String(64), nullable=False)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # Required, Optional, or Hidden
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="Optional")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<PaymentFieldConfig field={self.field_name} visibility={self.visibility}>"
