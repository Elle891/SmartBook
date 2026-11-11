"""Cashier accounts and transactions

Revision ID: tenant_0002
Revises: tenant_0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tenant_0002"
down_revision = "tenant_0001"
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
        "cashier_accounts",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("account_code", sa.String(32), nullable=False),
        sa.Column("cashier_type", sa.String(16), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("multi_currency_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cashier_accounts_account_set_id", "cashier_accounts", ["account_set_id"])
    op.create_unique_constraint(
        "uq_cashier_account", "cashier_accounts", ["account_set_id", "account_code"]
    )

    op.create_table(
        "cashier_transactions",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("voucher_id", uid, sa.ForeignKey("vouchers.id"), nullable=True),
        sa.Column("transaction_type", sa.String(16), nullable=False),
        sa.Column("primary_account_code", sa.String(32), nullable=False),
        sa.Column("counterparty_account_code", sa.String(32), nullable=True),
        sa.Column("from_account_code", sa.String(32), nullable=True),
        sa.Column("to_account_code", sa.String(32), nullable=True),
        sa.Column("period_code", sa.String(8), nullable=False),
        sa.Column("description", sa.String(512), nullable=False, server_default=""),
        sa.Column("foreign_currency", sa.String(8), nullable=True),
        sa.Column("foreign_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=True),
        sa.Column("functional_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("income_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("expenditure_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_cashier_transactions_account_set_id", "cashier_transactions", ["account_set_id"]
    )
    op.create_index(
        "ix_cashier_transactions_period_code", "cashier_transactions", ["period_code"]
    )


def downgrade() -> None:
    op.drop_table("cashier_transactions")
    op.drop_table("cashier_accounts")
