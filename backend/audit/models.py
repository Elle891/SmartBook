"""
AuditLog SQLAlchemy model — append-only, no update or delete.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import GUID, JsonType
from models.platform_base import PlatformBase as Base


class AuditLog(Base):
    """Immutable audit trail record.

    This table is append-only: no UPDATE or DELETE operations are permitted
    at the application layer.  Database-level enforcement should be added via
    a trigger or RLS policy in production (PostgreSQL); MySQL relies on app layer.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    old_value: Mapped[dict | None] = mapped_column(JsonType(), nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JsonType(), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} user={self.user_id} "
            f"action={self.action} entity={self.entity_type}/{self.entity_id}>"
        )
