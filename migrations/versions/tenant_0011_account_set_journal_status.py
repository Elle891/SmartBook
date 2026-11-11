"""Add account_sets.journal_set_no and account_sets.status

Revision ID: tenant_0011
Revises: tenant_0010
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tenant_0011"
down_revision = "tenant_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account_sets",
        sa.Column("journal_set_no", sa.String(64), nullable=True),
    )
    op.add_column(
        "account_sets",
        sa.Column("status", sa.String(16), nullable=False, server_default="Active"),
    )
    # Backfill unique codes for existing rows from id prefix + name
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, name FROM account_sets")).fetchall()
    for row in rows:
        account_set_id, name = row[0], row[1]
        # Prefer a stable unique value derived from id
        code = f"JS-{str(account_set_id).replace('-', '')[:12].upper()}"
        connection.execute(
            sa.text(
                "UPDATE account_sets SET journal_set_no = :code WHERE id = :id"
            ),
            {"code": code, "id": account_set_id},
        )
    op.alter_column("account_sets", "journal_set_no", existing_type=sa.String(64), nullable=False)
    op.create_unique_constraint(
        "uq_account_sets_journal_set_no",
        "account_sets",
        ["journal_set_no"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_account_sets_journal_set_no", "account_sets", type_="unique")
    op.drop_column("account_sets", "status")
    op.drop_column("account_sets", "journal_set_no")
