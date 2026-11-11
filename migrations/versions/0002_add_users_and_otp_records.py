"""Add users and otp_records tables

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    # UUID column type: native UUID for PostgreSQL, String(36) for MySQL/SQLite
    if dialect == "postgresql":
        uuid_type = sa.dialects.postgresql.UUID(as_uuid=False)
        jsn = sa.dialects.postgresql.JSONB
    else:
        uuid_type = sa.String(36)
        jsn = sa.JSON()

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("mobile", sa.String(32), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "is_email_verified",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "is_mobile_verified",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "failed_login_attempts",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
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

    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_mobile", "users", ["mobile"], unique=True)

    # ── otp_records ───────────────────────────────────────────────────────────
    op.create_table(
        "otp_records",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("otp_hash", sa.String(255), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column(
            "is_used", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_otp_records_target", "otp_records", ["target"])
    op.create_index(
        "ix_otp_records_lookup",
        "otp_records",
        ["target", "purpose", "session_id", "is_used"],
    )

    # ── audit_logs (platform auth / security events) ──────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(128), nullable=False),
        sa.Column("entity_id", sa.String(256), nullable=True),
        sa.Column("old_value", jsn, nullable=True),
        sa.Column("new_value", jsn, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_otp_records_lookup", table_name="otp_records")
    op.drop_index("ix_otp_records_target", table_name="otp_records")
    op.drop_table("otp_records")

    op.drop_index("ix_users_mobile", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
