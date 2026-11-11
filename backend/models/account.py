"""
Account SQLAlchemy model — Chart of Accounts per Account Set.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID, JsonType


class Account(Base):
    """A single account in the Chart of Accounts hierarchy.

    Supports up to 4 levels of nesting via parent_code self-reference.
    """

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Asset, Liability, Equity, Revenue, Expense
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # CAS or IFRS
    standard: Mapped[str] = mapped_column(String(8), nullable=False)
    parent_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_leaf: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Auxiliary dimensions enabled on this account (leaf only)
    # e.g. ["department", "project", "customer", "supplier", "employee"]
    aux_dimensions: Mapped[list] = mapped_column(
        JsonType, nullable=False, default=list
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
        return f"<Account {self.code} '{self.name}' set={self.account_set_id}>"
