"""
AccountSet, AccountSetRole, AccountSetMember SQLAlchemy async models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID, JsonType


class AccountSet(Base):
    """An isolated accounting entity for one enterprise."""

    __tablename__ = "account_sets"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Business code for the account set (Journal Set No.)
    journal_set_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # CAS or IFRS
    standard: Mapped[str] = mapped_column(String(8), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    start_period: Mapped[str] = mapped_column(String(8), nullable=False)
    # Shared or Individual
    datasource_type: Mapped[str] = mapped_column(String(16), nullable=False, default="Shared")
    # Active or Closed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Active")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
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
        return (
            f"<AccountSet id={self.id} name={self.name} "
            f"journal_set_no={self.journal_set_no} status={self.status}>"
        )


class AccountSetRole(Base):
    """A named permission set scoped to a single AccountSet."""

    __tablename__ = "account_set_roles"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # JSON array of permission strings
    permissions: Mapped[list] = mapped_column(JsonType, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<AccountSetRole id={self.id} name={self.name}>"


class AccountSetMember(Base):
    """Association between a user and an AccountSet with a role."""

    __tablename__ = "account_set_members"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_set_roles.id"), nullable=False, index=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<AccountSetMember account_set={self.account_set_id} user={self.user_id}>"
