"""
Registry service — tenant DB config lookup with Redis caching.

Public API:
    get_tenant_db_config(account_set_id) -> TenantDbConfig
    register_tenant(account_set_id, db_type, db_config) -> TenantRegistry
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from platform.db_config import platform_engine_connect_args, resolve_platform_db_url
from platform.registry.models import DbType, TenantRegistry, TenantStatus
from platform.vault_client import get_vault_client

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300  # 5 minutes

# Registry DB connection (platform-level, not tenant-level)
_REGISTRY_DB_URL = resolve_platform_db_url()
_registry_engine = create_async_engine(
    _REGISTRY_DB_URL,
    # aiomysql + SQLAlchemy pool_pre_ping currently fails with:
    # ping() missing 1 required positional argument: 'reconnect'
    pool_pre_ping=not _REGISTRY_DB_URL.startswith("mysql"),
    connect_args=platform_engine_connect_args(),
)
_registry_session_factory = async_sessionmaker(_registry_engine, expire_on_commit=False)

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


@dataclass
class TenantDbConfig:
    """Resolved database connection config for a tenant."""

    account_set_id: str
    db_type: DbType
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str  # fetched from Vault at resolution time
    credentials_vault_path: str
    status: str

    def async_url(self) -> str:
        """Build an async SQLAlchemy connection URL."""
        if self.db_type == DbType.postgresql:
            driver = "asyncpg"
        elif self.db_type == DbType.mysql:
            driver = "aiomysql"
        else:
            # sqlite — dev/test only
            return f"sqlite+aiosqlite:///{self.db_name}"
        return (
            f"{self.db_type.value}+{driver}://"
            f"{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )


def _cache_key(account_set_id: str) -> str:
    return f"tenant_db_config:{account_set_id}"


async def _get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    return aioredis.from_url(_REDIS_URL, decode_responses=True)


async def get_tenant_db_config(account_set_id: str) -> TenantDbConfig:
    """
    Return the database config for *account_set_id*.

    Results are cached in Redis for 5 minutes. The db_password is fetched
    from Vault and is NOT stored in the cache.
    """
    redis = await _get_redis()
    cache_key = _cache_key(account_set_id)

    # Try cache first (password excluded from cache)
    cached = await redis.get(cache_key)
    if cached:
        data = json.loads(cached)
        # Fetch password from Vault on every cache hit (not cached for security)
        vault = get_vault_client()
        secret = vault.read_secret(data["credentials_vault_path"])
        data["db_password"] = secret["db_password"]
        logger.debug("tenant_db_config cache hit for %s", account_set_id)
        return TenantDbConfig(**data)

    # Cache miss — query registry DB
    async with _registry_session_factory() as session:
        row = await _fetch_registry_row(session, account_set_id)

    vault = get_vault_client()
    secret = vault.read_secret(row.credentials_vault_path)
    db_password = secret["db_password"]

    config = TenantDbConfig(
        account_set_id=row.account_set_id,
        db_type=row.db_type,
        db_host=row.db_host,
        db_port=row.db_port,
        db_name=row.db_name,
        db_user=row.db_user,
        db_password=db_password,
        credentials_vault_path=row.credentials_vault_path,
        status=row.status.value,
    )

    # Cache without password
    cacheable = asdict(config)
    cacheable.pop("db_password")
    await redis.setex(cache_key, _CACHE_TTL_SECONDS, json.dumps(cacheable))
    logger.debug("tenant_db_config cached for %s", account_set_id)

    return config


async def _fetch_registry_row(session: AsyncSession, account_set_id: str) -> TenantRegistry:
    result = await session.execute(
        select(TenantRegistry).where(TenantRegistry.account_set_id == account_set_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"No tenant registry entry for account_set_id={account_set_id!r}")
    return row


async def register_tenant(
    account_set_id: str,
    db_type: DbType,
    db_config: dict,
) -> TenantRegistry:
    """
    Register a new tenant in the platform registry.

    *db_config* must contain: db_host, db_port, db_name, db_user, db_password.
    The password is stored in Vault; only the vault path is persisted in the DB.
    """
    vault_path = f"tenant-db/{account_set_id}"
    vault = get_vault_client()
    vault.write_secret(vault_path, {"db_password": db_config["db_password"]})

    row = TenantRegistry(
        account_set_id=account_set_id,
        db_type=db_type,
        db_host=db_config["db_host"],
        db_port=int(db_config["db_port"]),
        db_name=db_config["db_name"],
        db_user=db_config["db_user"],
        credentials_vault_path=vault_path,
        provisioned_at=datetime.utcnow(),
        status=TenantStatus.provisioning,
    )

    async with _registry_session_factory() as session:
        session.add(row)
        await session.commit()
        await session.refresh(row)

    logger.info("Tenant registered: account_set_id=%s db_type=%s", account_set_id, db_type)
    return row


async def update_tenant_status(account_set_id: str, status: TenantStatus) -> None:
    """Update the provisioning status of a tenant."""
    async with _registry_session_factory() as session:
        row = await _fetch_registry_row(session, account_set_id)
        row.status = status
        await session.commit()

    # Invalidate cache
    redis = await _get_redis()
    await redis.delete(_cache_key(account_set_id))
    logger.info("Tenant status updated: %s → %s", account_set_id, status)


async def list_all_tenants() -> list[TenantRegistry]:
    """Return all tenant registry rows (used by platform-admin CLI)."""
    async with _registry_session_factory() as session:
        result = await session.execute(select(TenantRegistry))
        return list(result.scalars().all())
