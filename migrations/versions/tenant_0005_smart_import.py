"""Add smart import tables

Revision ID: tenant_0005
Revises: tenant_0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tenant_0005"
down_revision = "tenant_0004"
branch_labels = None
depends_on = None


def _uuid(dialect: str) -> sa.types.TypeEngine:
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import UUID

        return UUID(as_uuid=False)
    return sa.String(36)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uid = _uuid(dialect)

    op.create_table(
        "import_sessions",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("file_name", sa.String(512), nullable=False),
        sa.Column("file_format", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="Uploaded"),
        sa.Column("total_records", sa.Integer, nullable=False, server_default="0"),
        sa.Column("vouchers_generated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(36), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_import_sessions_account_set_id", "import_sessions", ["account_set_id"])

    op.create_table(
        "import_transactions",
        sa.Column("id", uid, primary_key=True),
        sa.Column("session_id", uid, sa.ForeignKey("import_sessions.id"), nullable=False),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("txn_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("counterparty", sa.String(255), nullable=False, server_default=""),
        sa.Column("description", sa.String(512), nullable=False, server_default=""),
        sa.Column("reference_number", sa.String(128), nullable=False, server_default=""),
        sa.Column("suggested_debit_account", sa.String(32), nullable=False, server_default=""),
        sa.Column("suggested_credit_account", sa.String(32), nullable=False, server_default=""),
        sa.Column("mapped_debit_account", sa.String(32), nullable=True),
        sa.Column("mapped_credit_account", sa.String(32), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="Pending"),
        sa.Column("voucher_id", uid, sa.ForeignKey("vouchers.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "account_set_id",
            "txn_date",
            "amount",
            "reference_number",
            name="uq_import_txn_dedup",
        ),
    )
    op.create_index("ix_import_transactions_session_id", "import_transactions", ["session_id"])
    op.create_index("ix_import_transactions_account_set_id", "import_transactions", ["account_set_id"])
    op.create_index("ix_import_transactions_txn_date", "import_transactions", ["txn_date"])
    op.create_index("ix_import_transactions_voucher_id", "import_transactions", ["voucher_id"])


def downgrade() -> None:
    op.drop_table("import_transactions")
    op.drop_table("import_sessions")
