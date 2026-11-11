"""
Tenant-scoped audit log (append-only). Distinct from platform auth audit in audit/models.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID, JsonType


class TenantAuditLog(Base):
    """Immutable audit trail for accounting operations within a tenant DB."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    old_value: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
