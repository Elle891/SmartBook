"""Add payment_scope to payments

Revision ID: tenant_0007
Revises: tenant_0006
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tenant_0007"
down_revision = "tenant_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("payment_scope", sa.String(16), nullable=False, server_default="Domestic"),
    )


def downgrade() -> None:
    op.drop_column("payments", "payment_scope")
