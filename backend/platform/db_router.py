"""
DB Router middleware.

Reads `account_set_id` from the JWT bearer token, looks up the tenant's
database config via the registry (Redis-cached), and injects an async
SQLAlchemy engine into the request state.

Usage in route handlers:
    from platform.db_router import get_tenant_engine
    engine = request.state.tenant_engine
    # or via FastAPI dependency:
    engine = Depends(get_tenant_engine)
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Request
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from platform.db_config import (
    get_platform_db_type,
    platform_engine_connect_args,
    resolve_platform_db_url,
    resolve_shared_tenant_db_url,
)
from platform.db_instrumentation import instrument_engine
from platform.registry.models import DbType
from platform.registry.service import TenantDbConfig, get_tenant_db_config

logger = logging.getLogger(__name__)

_JWT_PUBLIC_KEY = os.environ.get("JWT_PUBLIC_KEY", "")
_JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "RS256")

# Per-tenant engine pool cache: account_set_id → AsyncEngine
_engine_pool: dict[str, AsyncEngine] = {}
_shared_engine: AsyncEngine | None = None

# Pool size limits per DB type
_POOL_CONFIG: dict[DbType, dict[str, int]] = {
    DbType.postgresql: {"pool_size": 10, "max_overflow": 0, "pool_min_size": 2},
    DbType.mysql: {"pool_size": 8, "max_overflow": 0, "pool_min_size": 2},
    DbType.sqlite: {"pool_size": 5, "max_overflow": 0, "pool_min_size": 1},
}

# Paths that don't require a tenant DB (auth, health, metrics, MCP)
_BYPASS_PATHS = {"/health", "/metrics", "/docs", "/redoc", "/openapi.json", "/mcp"}
_BYPASS_PREFIXES = ("/auth/", "/mcp/")

# Account-set bootstrap routes may run before JWT carries an account_set_id
_SHARED_TENANT_PREFIXES = ("/account-sets",)
_SHARED_TENANT_SENTINEL = "__shared__"


def _build_engine(config: TenantDbConfig) -> AsyncEngine:
    """Create and cache an async SQLAlchemy engine for the given tenant config."""
    pool_cfg = _POOL_CONFIG.get(config.db_type, _POOL_CONFIG[DbType.postgresql])

    connect_args: dict[str, Any] = {}
    if config.db_type == DbType.mysql:
        connect_args["charset"] = "utf8mb4"

    engine = create_async_engine(
        config.async_url(),
        pool_size=pool_cfg["pool_size"],
        max_overflow=pool_cfg["max_overflow"],
        # aiomysql + SQLAlchemy pool_pre_ping currently fails with:
        # ping() missing 1 required positional argument: 'reconnect'
        pool_pre_ping=config.db_type != DbType.mysql,
        connect_args=connect_args,
    )
    instrument_engine(engine.sync_engine, tenant_db=config.db_name)  # type: ignore[arg-type]
    return engine


def _get_or_create_engine(config: TenantDbConfig) -> AsyncEngine:
    """Return a cached engine or create a new one for the tenant."""
    account_set_id = config.account_set_id
    if account_set_id not in _engine_pool:
        _engine_pool[account_set_id] = _build_engine(config)
        logger.info(
            "Created engine pool for account_set_id=%s db_type=%s",
            account_set_id,
            config.db_type,
        )
    return _engine_pool[account_set_id]


def _decode_account_set_id(authorization: str) -> str | None:
    """Extract account_set_id claim from a Bearer JWT. Returns None on failure.

    Signature verification is intentionally skipped here — ``get_current_user``
    already verifies the token. This middleware only needs the claim for routing.
    """
    if not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):]
    try:
        # Prefer unverified claims API (jose) — avoids key/algorithm mismatch
        # between auth (RS256) and optional JWT_ALGORITHM env overrides.
        payload = jwt.get_unverified_claims(token)
        account_set_id = payload.get("account_set_id") or None
        if isinstance(account_set_id, str):
            account_set_id = account_set_id.strip() or None
        return account_set_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("JWT claim extract failed: %s", exc)
        return None


def _shared_tenant_db_type() -> DbType:
    return DbType.mysql if get_platform_db_type() == "mysql" else DbType.postgresql


def _get_shared_tenant_engine() -> AsyncEngine:
    """Engine for the shared multi-tenant DB (bootstrap Account Set create/list)."""
    global _shared_engine
    if _shared_engine is None:
        url = resolve_shared_tenant_db_url()
        db_type = _shared_tenant_db_type()
        connect_args: dict[str, Any] = {}
        if db_type == DbType.mysql:
            connect_args["charset"] = "utf8mb4"
        pool_cfg = _POOL_CONFIG.get(db_type, _POOL_CONFIG[DbType.postgresql])
        _shared_engine = create_async_engine(
            url,
            pool_size=pool_cfg["pool_size"],
            max_overflow=pool_cfg["max_overflow"],
            pool_pre_ping=db_type != DbType.mysql,
            connect_args=connect_args,
        )
        instrument_engine(_shared_engine.sync_engine, tenant_db="smartbook_shared")  # type: ignore[arg-type]
        logger.info("Created shared tenant engine url=%s", url.split("@")[-1])
    return _shared_engine


def _wants_shared_tenant(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _SHARED_TENANT_PREFIXES)


_tenant_session_factories: dict[str, Any] = {}


def _get_tenant_session_factory(engine: AsyncEngine) -> Any:
    """Return an async sessionmaker cached per engine URL."""
    key = str(engine.url)
    if key not in _tenant_session_factories:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        _tenant_session_factories[key] = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _tenant_session_factories[key]


class TenantDBMiddleware(BaseHTTPMiddleware):
    """
    Resolves tenant DB per request and injects ``request.state.db`` (AsyncSession).

    Also sets ``request.state.tenant_engine`` and ``request.state.account_set_id``.
    PostgreSQL tenants get RLS session variable ``app.current_account_set_id``.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        if request.url.path in _BYPASS_PATHS:
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in _BYPASS_PREFIXES):
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        account_set_id = _decode_account_set_id(authorization) if authorization else None

        request.state.tenant_engine = None
        request.state.account_set_id = None
        request.state.db = None
        request.state.tenant_db_type = None

        # First Account Set create/list: JWT has empty account_set_id — use shared DB
        if not account_set_id and _wants_shared_tenant(request.url.path):
            try:
                engine = _get_shared_tenant_engine()
                factory = _get_tenant_session_factory(engine)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to resolve shared tenant engine: %s", exc)
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Shared tenant database unavailable"},
                )
            request.state.tenant_engine = engine
            request.state.account_set_id = _SHARED_TENANT_SENTINEL
            request.state.tenant_db_type = _shared_tenant_db_type()
            async with factory() as session:
                request.state.db = session
                try:
                    response = await call_next(request)
                    await session.commit()
                    return response
                except Exception:
                    await session.rollback()
                    raise

        if not account_set_id:
            return await call_next(request)

        try:
            config = await get_tenant_db_config(account_set_id)
            engine = _get_or_create_engine(config)
            factory = _get_tenant_session_factory(engine)
        except KeyError:
            # Shared Account Sets may lack a registry row (registration race / legacy).
            # Fall back to the shared multi-tenant DB so switched JWTs still work.
            logger.warning(
                "No registry entry for account_set_id=%s; using shared tenant DB",
                account_set_id,
            )
            try:
                engine = _get_shared_tenant_engine()
                factory = _get_tenant_session_factory(engine)
                request.state.tenant_engine = engine
                request.state.account_set_id = account_set_id
                request.state.tenant_db_type = _shared_tenant_db_type()
                async with factory() as session:
                    from models.tenant_context import apply_tenant_context

                    await apply_tenant_context(
                        session, account_set_id, request.state.tenant_db_type
                    )
                    request.state.db = session
                    try:
                        response = await call_next(request)
                        await session.commit()
                        return response
                    except Exception:
                        await session.rollback()
                        raise
            except Exception as exc:  # noqa: BLE001
                logger.error("Shared tenant fallback failed: %s", exc)
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Shared tenant database unavailable"},
                )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to resolve tenant engine: %s", exc)
            return JSONResponse(
                status_code=503,
                content={"detail": "Tenant database unavailable"},
            )

        request.state.tenant_engine = engine
        request.state.account_set_id = account_set_id
        request.state.tenant_db_type = config.db_type

        async with factory() as session:
            from models.tenant_context import apply_tenant_context

            await apply_tenant_context(session, account_set_id, config.db_type)
            request.state.db = session
            try:
                response = await call_next(request)
                await session.commit()
                return response
            except Exception:
                await session.rollback()
                raise


async def get_tenant_db(request: Request) -> AsyncGenerator[Any, None]:
    """FastAPI dependency: reuse tenant session from middleware when present."""
    session = getattr(request.state, "db", None)
    if session is not None:
        yield session
        return

    engine = getattr(request.state, "tenant_engine", None)
    account_set_id = getattr(request.state, "account_set_id", None)
    db_type = getattr(request.state, "tenant_db_type", None)
    if engine is None or not account_set_id:
        # Last-chance shared fallback for Account Set bootstrap
        if _wants_shared_tenant(request.url.path):
            engine = _get_shared_tenant_engine()
            account_set_id = _SHARED_TENANT_SENTINEL
            db_type = _shared_tenant_db_type()
        else:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=401,
                detail="Missing or invalid account_set_id in JWT",
            )

    factory = _get_tenant_session_factory(engine)
    async with factory() as session:
        from models.tenant_context import apply_tenant_context

        if db_type is not None:
            await apply_tenant_context(session, account_set_id, db_type)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_tenant_engine(request: Request) -> AsyncEngine:
    """
    FastAPI dependency that returns the tenant's async engine from request state.

    Raises HTTP 401 if no account_set_id is present in the JWT.
    """
    from fastapi import HTTPException

    engine: AsyncEngine | None = getattr(request.state, "tenant_engine", None)
    if engine is None:
        raise HTTPException(status_code=401, detail="Missing or invalid account_set_id in JWT")
    return engine


@asynccontextmanager
async def open_tenant_session(account_set_id: str) -> AsyncGenerator[Any, None]:
    """Open a tenant AsyncSession outside the HTTP request cycle (e.g. MCP tools)."""
    config = await get_tenant_db_config(account_set_id)
    engine = _get_or_create_engine(config)
    factory = _get_tenant_session_factory(engine)
    async with factory() as session:
        from models.tenant_context import apply_tenant_context

        await apply_tenant_context(session, account_set_id, config.db_type)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Platform-level DB session (for auth routes without tenant context) ────────

_platform_engine: AsyncEngine | None = None


def _get_platform_engine() -> AsyncEngine:
    """Return (or create) the platform-level async engine."""
    global _platform_engine
    if _platform_engine is None:
        _platform_engine = create_async_engine(
            resolve_platform_db_url(),
            pool_size=5,
            max_overflow=0,
            # aiomysql + SQLAlchemy pool_pre_ping currently fails with:
            # ping() missing 1 required positional argument: 'reconnect'
            pool_pre_ping=get_platform_db_type() != "mysql",
            connect_args=platform_engine_connect_args(),
        )
    return _platform_engine


_platform_session_factory: Any | None = None


def _get_platform_session_factory():
    """Lazy-init async session factory for the platform registry database."""
    global _platform_session_factory
    if _platform_session_factory is None:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        _platform_session_factory = async_sessionmaker(
            _get_platform_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _platform_session_factory


async def get_platform_db() -> AsyncGenerator[Any, None]:
    """FastAPI dependency: platform-level AsyncSession for /auth/* routes.

    Users and OTP records live in the platform registry database, not tenant DBs.
    Commits on success, rolls back on error.
    """
    factory = _get_platform_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
