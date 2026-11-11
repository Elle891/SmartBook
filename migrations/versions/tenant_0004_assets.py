"""Add declining_balance_rate to fixed_assets

Revision ID: tenant_0004
Revises: tenant_0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tenant_0004"
down_revision = "tenant_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fixed_assets",
        sa.Column("declining_balance_rate", sa.Numeric(8, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fixed_assets", "declining_balance_rate")
