"""
Tenant database provisioner.

provision_tenant_database(account_set_id, db_type, db_config?)
  1. Creates the tenant database (PostgreSQL: CREATE DATABASE; MySQL: CREATE SCHEMA)
  2. Runs Alembic migrations against the new database
  3. Seeds the standard chart of accounts template
  4. Registers the tenant in the platform registry
  5. Updates tenant status to 'active'

Must complete in < 30 seconds.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from platform.registry.models import DbType, TenantStatus
from platform.registry.service import register_tenant, update_tenant_status

logger = logging.getLogger(__name__)

_PROVISION_TIMEOUT_SECONDS = 28  # leave 2 s buffer under the 30 s SLA

# Platform-level admin DB URLs used to CREATE the tenant database
_PG_ADMIN_URL = os.environ.get(
    "PG_ADMIN_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
)
_MYSQL_ADMIN_URL = os.environ.get(
    "MYSQL_ADMIN_URL", "mysql+aiomysql://root:root@localhost:3306/mysql"
)

# Default DB host/port/user for platform-provisioned (shared) databases
_PG_HOST = os.environ.get("PG_HOST", "localhost")
_PG_PORT = int(os.environ.get("PG_PORT", "5432"))
_PG_USER = os.environ.get("PG_USER", "postgres")
_PG_PASSWORD = os.environ.get("PG_PASSWORD", "postgres")

_MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
_MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
_MYSQL_USER = os.environ.get("MYSQL_USER", "root")
_MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "root")

# Path to the Alembic config (relative to repo root)
_ALEMBIC_INI = os.environ.get("ALEMBIC_INI", "migrations/alembic.ini")


async def provision_tenant_database(
    account_set_id: str,
    db_type: DbType,
    db_config: dict[str, Any] | None = None,
    accounting_standard: str = "CAS",
) -> dict[str, Any]:
    """
    Provision a new tenant database.

    Args:
        account_set_id: The Account Set UUID.
        db_type: DbType.postgresql or DbType.mysql.
        db_config: For Individual datasource — caller-supplied connection params.
                   For Shared datasource — omit; platform generates the DB.
        accounting_standard: "CAS" or "IFRS" — determines which chart of accounts
                             template is seeded.

    Returns:
        dict with db_host, db_port, db_name, db_user (no password).

    Raises:
        TimeoutError: If provisioning exceeds 28 seconds.
        RuntimeError: On any provisioning failure.
    """
    start = time.monotonic()

    try:
        result = await asyncio.wait_for(
            _provision(account_set_id, db_type, db_config, accounting_standard),
            timeout=_PROVISION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError(
            f"Tenant provisioning exceeded {_PROVISION_TIMEOUT_SECONDS}s for "
            f"account_set_id={account_set_id}"
        ) from exc

    elapsed = time.monotonic() - start
    logger.info(
        "Tenant provisioned in %.2fs: account_set_id=%s db_type=%s",
        elapsed,
        account_set_id,
        db_type,
    )
    return result


async def _provision(
    account_set_id: str,
    db_type: DbType,
    db_config: dict[str, Any] | None,
    accounting_standard: str,
) -> dict[str, Any]:
    """Internal provisioning logic (no timeout wrapper)."""

    # 1. Resolve connection params
    if db_config:
        # Individual datasource — user-supplied connection
        resolved = dict(db_config)
    else:
        # Shared datasource — platform generates a new DB
        db_name = f"tenant_{account_set_id.replace('-', '_')}"
        if db_type == DbType.postgresql:
            resolved = {
                "db_host": _PG_HOST,
                "db_port": _PG_PORT,
                "db_name": db_name,
                "db_user": _PG_USER,
                "db_password": _PG_PASSWORD,
            }
        elif db_type == DbType.mysql:
            resolved = {
                "db_host": _MYSQL_HOST,
                "db_port": _MYSQL_PORT,
                "db_name": db_name,
                "db_user": _MYSQL_USER,
                "db_password": _MYSQL_PASSWORD,
            }
        else:
            # SQLite — dev/test only
            resolved = {
                "db_host": "localhost",
                "db_port": 0,
                "db_name": f"/tmp/{db_name}.db",
                "db_user": "",
                "db_password": "",
            }

    # 2. Register tenant in registry (status=provisioning)
    await register_tenant(account_set_id, db_type, resolved)

    # 3. Create the physical database (skip for SQLite and Individual datasource)
    if not db_config and db_type != DbType.sqlite:
        await _create_database(db_type, resolved["db_name"])

    # 4. Run Alembic migrations
    await _run_migrations(account_set_id, db_type, resolved)

    # 5. Seed chart of accounts template
    await _seed_chart_of_accounts(account_set_id, db_type, resolved, accounting_standard)

    # 5b. Seed default payment transaction type (Standard)
    await _seed_payment_transaction_type(account_set_id)

    # 5c. Seed default ISO 20022 field configurations
    await _seed_payment_field_configs(account_set_id)

    # 6. Mark tenant as active
    await update_tenant_status(account_set_id, TenantStatus.active)

    return {
        "db_host": resolved["db_host"],
        "db_port": resolved["db_port"],
        "db_name": resolved["db_name"],
        "db_user": resolved["db_user"],
    }


async def _create_database(db_type: DbType, db_name: str) -> None:
    """Create the physical database using an admin connection."""
    if db_type == DbType.postgresql:
        admin_engine = create_async_engine(
            _PG_ADMIN_URL,
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
        )
        async with admin_engine.connect() as conn:
            # Check if DB already exists
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            )
            if not result.scalar():
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                logger.info("Created PostgreSQL database: %s", db_name)
        await admin_engine.dispose()

    elif db_type == DbType.mysql:
        admin_engine = create_async_engine(
            _MYSQL_ADMIN_URL,
            pool_pre_ping=True,
        )
        async with admin_engine.connect() as conn:
            await conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
            logger.info("Created MySQL database: %s", db_name)
        await admin_engine.dispose()


async def _run_migrations(
    account_set_id: str, db_type: DbType, resolved: dict[str, Any]
) -> None:
    """Run Alembic migrations against the tenant database."""
    import subprocess

    from platform.registry.service import TenantDbConfig

    config = TenantDbConfig(
        account_set_id=account_set_id,
        db_type=db_type,
        db_host=resolved["db_host"],
        db_port=resolved["db_port"],
        db_name=resolved["db_name"],
        db_user=resolved["db_user"],
        db_password=resolved["db_password"],
        credentials_vault_path=f"tenant-db/{account_set_id}",
        status=TenantStatus.provisioning.value,
    )
    db_url = config.async_url()
    # Alembic needs a sync URL for the subprocess
    sync_url = db_url.replace("+asyncpg", "").replace("+aiomysql", "+pymysql")

    env = {**os.environ, "TENANT_DB_URL": sync_url, "MIGRATION_SCOPE": "tenant"}
    proc = await asyncio.create_subprocess_exec(
        "alembic",
        "-c",
        _ALEMBIC_INI,
        "upgrade",
        "tenant_0001",
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"Alembic migration failed for {account_set_id}:\n"
            f"stdout: {stdout.decode()}\nstderr: {stderr.decode()}"
        )
    logger.info("Migrations applied for account_set_id=%s", account_set_id)


async def _seed_chart_of_accounts(
    account_set_id: str,
    db_type: DbType,
    resolved: dict[str, Any],
    accounting_standard: str,
) -> None:
    """
    Seed the standard chart of accounts template into the tenant database.

    The actual seeding is delegated to the account_set module once it exists.
    For now we log the intent; the account_set service will call this after
    the models are defined in task 5/6.
    """
    logger.info(
        "Seeding %s chart of accounts for account_set_id=%s",
        accounting_standard,
        account_set_id,
    )
    # Deferred: account_set.templates will be imported here in task 6
    # from account_set.templates import seed_template
    # await seed_template(account_set_id, accounting_standard, resolved)


async def _seed_payment_transaction_type(account_set_id: str) -> None:
    """Seed Standard PaymentTransactionType in the tenant DB (Task 24a)."""
    from payment.transaction_type_service import ensure_standard_transaction_type
    from payroll.runner import with_tenant_session

    async def _run(db):  # noqa: ANN001
        await ensure_standard_transaction_type(db, account_set_id=account_set_id)

    try:
        await with_tenant_session(account_set_id, _run)
        logger.info("Seeded Standard payment transaction type for account_set_id=%s", account_set_id)
    except Exception as exc:
        logger.warning(
            "Payment transaction type seed skipped for %s: %s", account_set_id, exc
        )


async def _seed_payment_field_configs(account_set_id: str) -> None:
    """Seed default ISO 20022 field configs in tenant DB (Task 25)."""
    from payment.field_config_service import seed_default_field_configs
    from payroll.runner import with_tenant_session

    async def _run(db):  # noqa: ANN001
        await seed_default_field_configs(db, account_set_id=account_set_id)

    try:
        await with_tenant_session(account_set_id, _run)
        logger.info("Seeded payment field configs for account_set_id=%s", account_set_id)
    except Exception as exc:
        logger.warning(
            "Payment field config seed skipped for %s: %s", account_set_id, exc
        )
