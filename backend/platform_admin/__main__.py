"""
platform-admin CLI

Usage:
    python -m platform_admin migrate --tenant=all
    python -m platform_admin migrate --tenant=<account_set_id>
    python -m platform_admin list-tenants
    python -m platform_admin provision --tenant=<account_set_id> --db-type=postgresql

Runs Alembic migrations across all (or a specific) tenant DBs in parallel,
with a maximum of 10 concurrent migrations.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from platform.logging_config import get_logger
from platform.registry.models import DbType, TenantStatus
from platform.registry.service import (
    TenantDbConfig,
    get_tenant_db_config,
    list_all_tenants,
)

logger = get_logger("platform-admin")

_MAX_CONCURRENT_MIGRATIONS = 10
_ALEMBIC_INI = os.environ.get("ALEMBIC_INI", "migrations/alembic.ini")


# ── Migration ─────────────────────────────────────────────────────────────────


async def migrate_tenant(account_set_id: str, semaphore: asyncio.Semaphore) -> tuple[str, bool, str]:
    """
    Run Alembic `upgrade head` for a single tenant.

    Returns (account_set_id, success, message).
    """
    async with semaphore:
        try:
            config: TenantDbConfig = await get_tenant_db_config(account_set_id)
            db_url = config.async_url()
            # Alembic needs a synchronous URL
            sync_url = db_url.replace("+asyncpg", "").replace("+aiomysql", "+pymysql")

            env = {**os.environ, "TENANT_DB_URL": sync_url}
            proc = await asyncio.create_subprocess_exec(
                "alembic",
                "-c",
                _ALEMBIC_INI,
                "upgrade",
                "head",
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                logger.info("Migration OK: %s", account_set_id)
                return account_set_id, True, stdout.decode().strip()
            else:
                msg = stderr.decode().strip()
                logger.error("Migration FAILED: %s — %s", account_set_id, msg)
                return account_set_id, False, msg

        except Exception as exc:  # noqa: BLE001
            logger.error("Migration error for %s: %s", account_set_id, exc)
            return account_set_id, False, str(exc)


async def cmd_migrate(tenant: str) -> int:
    """Run migrations for one or all tenants. Returns exit code."""
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_MIGRATIONS)

    if tenant == "all":
        rows = await list_all_tenants()
        account_set_ids = [r.account_set_id for r in rows if r.status == TenantStatus.active]
        if not account_set_ids:
            print("No active tenants found.")
            return 0
        print(f"Migrating {len(account_set_ids)} tenant(s) (max {_MAX_CONCURRENT_MIGRATIONS} concurrent)...")
    else:
        account_set_ids = [tenant]
        print(f"Migrating tenant: {tenant}")

    tasks = [migrate_tenant(aid, semaphore) for aid in account_set_ids]
    results = await asyncio.gather(*tasks)

    ok = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]

    print(f"\n✓ {len(ok)} succeeded, ✗ {len(failed)} failed")
    for aid, _, msg in failed:
        print(f"  FAILED {aid}: {msg}")

    return 0 if not failed else 1


# ── List tenants ──────────────────────────────────────────────────────────────


async def cmd_list_tenants() -> int:
    rows = await list_all_tenants()
    if not rows:
        print("No tenants registered.")
        return 0
    print(f"{'account_set_id':<38} {'db_type':<12} {'status':<16} {'db_name'}")
    print("-" * 90)
    for r in rows:
        print(f"{r.account_set_id:<38} {r.db_type.value:<12} {r.status.value:<16} {r.db_name}")
    return 0


# ── Provision ─────────────────────────────────────────────────────────────────


async def cmd_provision(account_set_id: str, db_type_str: str, standard: str) -> int:
    from platform.provisioner import provision_tenant_database

    try:
        db_type = DbType(db_type_str)
    except ValueError:
        print(f"Invalid db-type: {db_type_str!r}. Choose: postgresql, mysql, sqlite")
        return 1

    print(f"Provisioning tenant {account_set_id} ({db_type_str}, {standard})...")
    try:
        result = await provision_tenant_database(account_set_id, db_type, accounting_standard=standard)
        print(f"✓ Provisioned: {result}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"✗ Provisioning failed: {exc}")
        return 1


# ── CLI entry point ───────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m platform_admin",
        description="Platform admin CLI for multi-tenant database management",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # migrate
    migrate_p = sub.add_parser("migrate", help="Run Alembic migrations")
    migrate_p.add_argument(
        "--tenant",
        required=True,
        metavar="ACCOUNT_SET_ID|all",
        help="Target tenant account_set_id, or 'all' for every active tenant",
    )

    # list-tenants
    sub.add_parser("list-tenants", help="List all registered tenants")

    # provision
    prov_p = sub.add_parser("provision", help="Provision a new tenant database")
    prov_p.add_argument("--tenant", required=True, metavar="ACCOUNT_SET_ID")
    prov_p.add_argument(
        "--db-type",
        default="postgresql",
        choices=["postgresql", "mysql", "sqlite"],
    )
    prov_p.add_argument(
        "--standard",
        default="CAS",
        choices=["CAS", "IFRS"],
        help="Accounting standard for chart of accounts seeding",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "migrate":
        exit_code = asyncio.run(cmd_migrate(args.tenant))
    elif args.command == "list-tenants":
        exit_code = asyncio.run(cmd_list_tenants())
    elif args.command == "provision":
        exit_code = asyncio.run(cmd_provision(args.tenant, args.db_type, args.standard))
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
