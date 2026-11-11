"""Extend forecast tables for Task 28

Revision ID: tenant_0009
Revises: tenant_0008
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tenant_0009"
down_revision = "tenant_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "forecast_periods",
        sa.Column("predicted_net_cash_flow", sa.Numeric(18, 4), nullable=False, server_default="0"),
    )
    op.alter_column("forecast_snapshots", "result_id", existing_type=sa.String(36), nullable=True)
    op.add_column("forecast_snapshots", sa.Column("snapshot_period", sa.String(8), nullable=True))
    op.add_column("forecast_snapshots", sa.Column("target_period", sa.String(8), nullable=True))
    op.add_column(
        "forecast_snapshots",
        sa.Column("predicted_net_cash_flow", sa.Numeric(18, 4), nullable=True),
    )
    op.add_column(
        "forecast_snapshots",
        sa.Column("confidence_lower", sa.Numeric(18, 4), nullable=True),
    )
    op.add_column(
        "forecast_snapshots",
        sa.Column("confidence_upper", sa.Numeric(18, 4), nullable=True),
    )
    op.add_column(
        "forecast_snapshots",
        sa.Column("actual_net_cash_flow", sa.Numeric(18, 4), nullable=True),
    )
    op.create_index(
        "ix_forecast_snapshots_snapshot_period",
        "forecast_snapshots",
        ["snapshot_period"],
    )
    op.create_index(
        "ix_forecast_snapshots_target_period",
        "forecast_snapshots",
        ["target_period"],
    )


def downgrade() -> None:
    op.drop_index("ix_forecast_snapshots_target_period", table_name="forecast_snapshots")
    op.drop_index("ix_forecast_snapshots_snapshot_period", table_name="forecast_snapshots")
    op.drop_column("forecast_snapshots", "actual_net_cash_flow")
    op.drop_column("forecast_snapshots", "confidence_upper")
    op.drop_column("forecast_snapshots", "confidence_lower")
    op.drop_column("forecast_snapshots", "predicted_net_cash_flow")
    op.drop_column("forecast_snapshots", "target_period")
    op.drop_column("forecast_snapshots", "snapshot_period")
    op.alter_column("forecast_snapshots", "result_id", existing_type=sa.String(36), nullable=False)
    op.drop_column("forecast_periods", "predicted_net_cash_flow")
