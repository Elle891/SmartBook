"""
Shared SQLAlchemy declarative base and dialect-agnostic column helpers for tenant DBs.

Platform auth models (User, OTPRecord) use models.platform_base.PlatformBase.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, String, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import CHAR


class Base(DeclarativeBase):
    """Metadata base for all tenant-scoped accounting tables."""


class GUID(TypeDecorator):
    """Platform-independent UUID type (PostgreSQL UUID, MySQL/SQLite CHAR(36))."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_GUID())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return str(value) if dialect.name != "postgresql" else value
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class JsonType(TypeDecorator):
    """JSONB on PostgreSQL, JSON on MySQL/SQLite."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(GUID(), primary_key=True, default=uuid.uuid4)


def account_set_id_col(*, index: bool = True) -> Mapped[uuid.UUID]:
    return mapped_column(
        GUID(),
        nullable=False,
        index=index,
    )
