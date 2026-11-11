"""Add report engine tables

Revision ID: tenant_0006
Revises: tenant_0005
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tenant_0006"
down_revision = "tenant_0005"
branch_labels = None
depends_on = None


def _uuid(dialect: str) -> sa.types.TypeEngine:
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import UUID

        return UUID(as_uuid=False)
    return sa.String(36)


def _json(dialect: str) -> sa.types.TypeEngine:
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB

        return JSONB()
    return sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uid = _uuid(dialect)
    jsn = _json(dialect)

    op.create_table(
        "report_data_sources",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("connection_mode", sa.String(16), nullable=False, server_default="Ledger"),
        sa.Column("vendor", sa.String(16), nullable=True),
        sa.Column("endpoint_url", sa.String(512), nullable=True),
        sa.Column("host", sa.String(255), nullable=True),
        sa.Column("port", sa.Integer, nullable=True),
        sa.Column("database_name", sa.String(128), nullable=True),
        sa.Column("credentials_ref", sa.String(512), nullable=True),
        sa.Column("config", jsn, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="Active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_report_data_sources_account_set_id", "report_data_sources", ["account_set_id"])

    op.create_table(
        "report_templates",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("data_source_id", uid, sa.ForeignKey("report_data_sources.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("layout", jsn, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="Draft"),
        sa.Column("published_role_ids", jsn, nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_report_templates_account_set_id", "report_templates", ["account_set_id"])

    op.create_table(
        "generated_reports",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("report_type", sa.String(32), nullable=False),
        sa.Column("standard", sa.String(8), nullable=False),
        sa.Column("filters", jsn, nullable=False, server_default="{}"),
        sa.Column("data", jsn, nullable=False, server_default="{}"),
        sa.Column("generated_by", sa.String(36), nullable=False, server_default=""),
        sa.Column("generation_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_generated_reports_account_set_id", "generated_reports", ["account_set_id"])


def downgrade() -> None:
    op.drop_table("generated_reports")
    op.drop_table("report_templates")
    op.drop_table("report_data_sources")
