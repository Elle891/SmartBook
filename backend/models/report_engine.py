"""
Report, ReportTemplate, ReportDataSource models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID, JsonType

TEMPLATE_DRAFT = "Draft"
TEMPLATE_PUBLISHED = "Published"

MODE_LEDGER = "Ledger"
MODE_API = "API"
MODE_DATA_SERVER = "DataServer"

VENDOR_MYSQL = "MySQL"
VENDOR_ORACLE = "Oracle"
VENDOR_SQLSERVER = "SQLServer"


class GeneratedReport(Base):
    __tablename__ = "generated_reports"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    report_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    standard: Mapped[str] = mapped_column(String(8), nullable=False)
    filters: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    data: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    generated_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    generation_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("report_data_sources.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    layout: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=TEMPLATE_DRAFT)
    published_role_ids: Mapped[Optional[list]] = mapped_column(JsonType, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
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


class ReportDataSource(Base):
    __tablename__ = "report_data_sources"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connection_mode: Mapped[str] = mapped_column(String(16), nullable=False, default=MODE_LEDGER)
    vendor: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    endpoint_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    database_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    credentials_ref: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    config: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
