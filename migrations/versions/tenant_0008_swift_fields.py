"""Add SWIFT / international payment fields to payments

Revision ID: tenant_0008
Revises: tenant_0007
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tenant_0008"
down_revision = "tenant_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("recipient_agent_bic", sa.String(11), nullable=True))
    op.add_column("payments", sa.Column("recipient_agent_name", sa.String(255), nullable=True))
    op.add_column("payments", sa.Column("recipient_agent_address", sa.Text(), nullable=True))
    op.add_column("payments", sa.Column("intermediary_agent_bic", sa.String(11), nullable=True))
    op.add_column("payments", sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=True))
    op.add_column("payments", sa.Column("charge_bearer", sa.String(8), nullable=True))
    op.add_column("payments", sa.Column("payment_purpose_code", sa.String(64), nullable=True))
    op.add_column("payments", sa.Column("remittance_info", sa.Text(), nullable=True))
    op.add_column("payments", sa.Column("end_to_end_id", sa.String(64), nullable=True))
    op.add_column("payments", sa.Column("actual_settlement_date", sa.Date(), nullable=True))
    op.add_column("payments", sa.Column("bank_reference", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "bank_reference")
    op.drop_column("payments", "actual_settlement_date")
    op.drop_column("payments", "end_to_end_id")
    op.drop_column("payments", "remittance_info")
    op.drop_column("payments", "payment_purpose_code")
    op.drop_column("payments", "charge_bearer")
    op.drop_column("payments", "exchange_rate")
    op.drop_column("payments", "intermediary_agent_bic")
    op.drop_column("payments", "recipient_agent_address")
    op.drop_column("payments", "recipient_agent_name")
    op.drop_column("payments", "recipient_agent_bic")
