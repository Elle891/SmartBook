"""
TenantRegistry SQLAlchemy model.

Maps each Account Set to its dedicated database connection info.
Credentials (db_password) are stored in Vault; only the vault path is kept here.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DbType(str, enum.Enum):
    postgresql = "postgresql"
    mysql = "mysql"
    sqlite = "sqlite"  # dev/test only


class TenantStatus(str, enum.Enum):
    provisioning = "provisioning"
    active = "active"
    suspended = "suspended"
    deprovisioned = "deprovisioned"


# Cross-dialect ENUM columns (PostgreSQL named types vs MySQL inline ENUM)
_db_type_enum = Enum(
    DbType,
    name="db_type_enum",
    native_enum=False,
    length=32,
    values_callable=lambda enum: [member.value for member in enum],
)
_tenant_status_enum = Enum(
    TenantStatus,
    name="tenant_status_enum",
    native_enum=False,
    length=32,
    values_callable=lambda enum: [member.value for member in enum],
)


class TenantRegistry(Base):
    """
    Central registry mapping account_set_id → tenant database connection info.

    One row per Account Set. Credentials are stored in Vault; only the
    vault path is persisted here.
    """

    __tablename__ = "tenant_registry"

    tenant_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_set_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True
    )
    db_type: Mapped[DbType] = mapped_column(_db_type_enum, nullable=False)
    db_host: Mapped[str] = mapped_column(String(255), nullable=False)
    db_port: Mapped[int] = mapped_column(Integer, nullable=False)
    db_name: Mapped[str] = mapped_column(String(255), nullable=False)
    db_user: Mapped[str] = mapped_column(String(255), nullable=False)
    # Path in Vault KV v2 where db_password is stored
    credentials_vault_path: Mapped[str] = mapped_column(String(512), nullable=False)
    provisioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[TenantStatus] = mapped_column(
        _tenant_status_enum,
        nullable=False,
        default=TenantStatus.provisioning,
    )

    def __repr__(self) -> str:
        return (
            f"<TenantRegistry account_set_id={self.account_set_id!r} "
            f"db_type={self.db_type} status={self.status}>"
        )
