"""Add NLP interaction log audit fields

Revision ID: tenant_0010
Revises: tenant_0009
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tenant_0010"
down_revision = "tenant_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nlp_interaction_logs", sa.Column("user_message", sa.Text(), nullable=True))
    op.add_column("nlp_interaction_logs", sa.Column("response_text", sa.Text(), nullable=True))
    op.add_column("nlp_interaction_logs", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("nlp_interaction_logs", sa.Column("model_used", sa.String(64), nullable=True))
    op.add_column("nlp_interaction_logs", sa.Column("rbac_check_passed", sa.Boolean(), nullable=True))
    op.add_column("nlp_interaction_logs", sa.Column("language", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("nlp_interaction_logs", "language")
    op.drop_column("nlp_interaction_logs", "rbac_check_passed")
    op.drop_column("nlp_interaction_logs", "model_used")
    op.drop_column("nlp_interaction_logs", "confidence")
    op.drop_column("nlp_interaction_logs", "response_text")
    op.drop_column("nlp_interaction_logs", "user_message")
