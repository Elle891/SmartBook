"""Initial tenant registry table

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    # Enum types — PostgreSQL requires explicit CREATE TYPE; MySQL uses inline ENUM
    if dialect == "postgresql":
        db_type_enum = sa.Enum(
            "postgresql", "mysql", "sqlite",
            name="db_type_enum",
            create_constraint=True,
        )
        tenant_status_enum = sa.Enum(
            "provisioning", "active", "suspended", "deprovisioned",
            name="tenant_status_enum",
            create_constraint=True,
        )
    else:
        # MySQL / SQLite — inline enum, no named type
        db_type_enum = sa.Enum("postgresql", "mysql", "sqlite")
        tenant_status_enum = sa.Enum("provisioning", "active", "suspended", "deprovisioned")

    op.create_table(
        "tenant_registry",
        sa.Column("tenant_id", sa.String(36), primary_key=True),
        sa.Column("account_set_id", sa.String(36), nullable=False),
        sa.Column("db_type", db_type_enum, nullable=False),
        sa.Column("db_host", sa.String(255), nullable=False),
        sa.Column("db_port", sa.Integer, nullable=False),
        sa.Column("db_name", sa.String(255), nullable=False),
        sa.Column("db_user", sa.String(255), nullable=False),
        sa.Column("credentials_vault_path", sa.String(512), nullable=False),
        sa.Column(
            "provisioned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("status", tenant_status_enum, nullable=False),
    )

    op.create_index(
        "ix_tenant_registry_account_set_id",
        "tenant_registry",
        ["account_set_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_registry_account_set_id", table_name="tenant_registry")
    op.drop_table("tenant_registry")

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TYPE IF EXISTS db_type_enum")
        op.execute("DROP TYPE IF EXISTS tenant_status_enum")
