"""
Alembic env.py — dialect-aware migration runner.

MIGRATION_SCOPE:
  - platform: tenant_registry + users/otp (revisions 0001, 0002)
  - tenant:   accounting schema (revision tenant_0001)

Set PLATFORM_DB_URL or TENANT_DB_URL for the target database.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_BACKEND_ROOT = os.path.join(_REPO_ROOT, "backend")
for path in (_REPO_ROOT, _BACKEND_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

from platform.db_config import resolve_platform_db_url_sync

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

MIGRATION_SCOPE = os.environ.get("MIGRATION_SCOPE", "tenant")


def _load_target_metadata():
    if MIGRATION_SCOPE == "platform":
        from platform.registry.models import Base

        return Base.metadata

    import models.account  # noqa: F401
    import models.account_set  # noqa: F401
    import models.assets  # noqa: F401
    import models.bank  # noqa: F401
    import models.ledger  # noqa: F401
    import models.ml  # noqa: F401
    import models.nlp  # noqa: F401
    import models.payment  # noqa: F401
    import models.payroll  # noqa: F401
    import models.reports  # noqa: F401
    import models.tenant_audit  # noqa: F401
    import models.voucher  # noqa: F401
    from models.base import Base

    return Base.metadata


target_metadata = _load_target_metadata()


def get_url() -> str:
    if MIGRATION_SCOPE == "platform":
        url = os.environ.get("PLATFORM_DB_URL") or os.environ.get("REGISTRY_DB_URL")
        if url:
            return url.replace("+asyncpg", "").replace("+aiomysql", "+pymysql")
        return resolve_platform_db_url_sync()
    url = os.environ.get("TENANT_DB_URL")
    if url:
        return url.replace("+asyncpg", "").replace("+aiomysql", "+pymysql")
    return config.get_main_option("sqlalchemy.url", "")


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = get_url()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        dialect_name: str = connection.dialect.name

        if dialect_name == "mysql":
            connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            transaction_per_migration=(dialect_name == "postgresql"),
            render_as_batch=(dialect_name == "sqlite"),
        )

        try:
            with context.begin_transaction():
                context.run_migrations()
        finally:
            if dialect_name == "mysql":
                connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
