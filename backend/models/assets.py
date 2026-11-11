"""
FixedAsset SQLAlchemy async model.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID, JsonType


class FixedAsset(Base):
    """A fixed asset tracked for depreciation."""

    __tablename__ = "fixed_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    acquisition_date: Mapped[date] = mapped_column(Date, nullable=False)
    cost: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    useful_life_months: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # StraightLine or DecliningBalance
    depreciation_method: Mapped[str] = mapped_column(String(32), nullable=False, default="StraightLine")
    # Monthly rate for declining-balance (e.g. 0.02 = 2% per month)
    declining_balance_rate: Mapped[Optional[float]] = mapped_column(
        Numeric(8, 6), nullable=True
    )
    accumulated_depreciation: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    net_book_value: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    is_disposed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disposed_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<FixedAsset id={self.id} name={self.name}>"
