"""Payroll extensions — settings, adjustments, distribution logs

Revision ID: tenant_0003
Revises: tenant_0002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tenant_0003"
down_revision = "tenant_0002"
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

    op.add_column("employees", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("employees", sa.Column("mobile", sa.String(32), nullable=True))

    op.create_table(
        "payroll_settings",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("rates", jsn, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payroll_settings_account_set_id", "payroll_settings", ["account_set_id"], unique=True)

    op.create_table(
        "payroll_adjustments",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("employee_id", uid, sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("period_code", sa.String(8), nullable=False),
        sa.Column("adjustment_type", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("description", sa.String(512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payroll_adjustments_account_set_id", "payroll_adjustments", ["account_set_id"])
    op.create_index("ix_payroll_adjustments_employee_id", "payroll_adjustments", ["employee_id"])
    op.create_index("ix_payroll_adjustments_period_code", "payroll_adjustments", ["period_code"])

    op.create_table(
        "payslip_distribution_logs",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("payroll_run_id", uid, sa.ForeignKey("payroll_runs.id"), nullable=False),
        sa.Column("employee_id", uid, sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("success", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("failure_reason", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("payroll_run_id", "employee_id", "channel", name="uq_payslip_dist_per_channel"),
    )


def downgrade() -> None:
    op.drop_table("payslip_distribution_logs")
    op.drop_table("payroll_adjustments")
    op.drop_table("payroll_settings")
    op.drop_column("employees", "mobile")
    op.drop_column("employees", "email")
