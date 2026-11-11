"""
User and OTPRecord SQLAlchemy async models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import GUID
from models.platform_base import PlatformBase as Base


class User(Base):
    """Registered user account."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    email: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    mobile: Mapped[str | None] = mapped_column(
        String(32), nullable=True, unique=True, index=True
    )
    # Null for mobile-only users before password is set
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_mobile_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
        return f"<User id={self.id} email={self.email} mobile={self.mobile}>"


class OTPRecord(Base):
    """One-time password record for email/mobile verification."""

    __tablename__ = "otp_records"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Email address or mobile number
    target: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # bcrypt hash of the 6-digit OTP
    otp_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # "register_email", "register_mobile", "login_mobile", "reset_email", "reset_mobile"
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Groups OTPs for the same session (to invalidate previous ones)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<OTPRecord id={self.id} target={self.target} "
            f"purpose={self.purpose} used={self.is_used}>"
        )
