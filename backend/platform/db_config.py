"""
Platform (registry) database URL resolution.

The platform center database stores tenant_registry, users, otp_records, and
audit_logs. It supports MySQL 8.0+ (default) and PostgreSQL.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote_plus

SUPPORTED_PLATFORM_DB_TYPES = frozenset({"postgresql", "mysql"})


def get_platform_db_type() -> str:
    """Return ``postgresql`` or ``mysql``."""
    explicit = os.environ.get("PLATFORM_DB_TYPE", "").strip().lower()
    if explicit:
        if explicit not in SUPPORTED_PLATFORM_DB_TYPES:
            raise ValueError(
                f"Unsupported PLATFORM_DB_TYPE={explicit!r}; "
                f"use one of: {', '.join(sorted(SUPPORTED_PLATFORM_DB_TYPES))}"
            )
        return explicit

    for key in ("PLATFORM_DB_URL", "REGISTRY_DB_URL", "DATABASE_URL"):
        url = os.environ.get(key, "")
        if url.startswith("mysql"):
            return "mysql"
        if url.startswith("postgresql") or url.startswith("postgres"):
            return "postgresql"
    return "mysql"


def resolve_platform_db_url() -> str:
    """
    Async SQLAlchemy URL for the platform registry database.

    Priority: PLATFORM_DB_URL / REGISTRY_DB_URL / DATABASE_URL, then composed
    from PLATFORM_DB_* parts when PLATFORM_DB_TYPE=mysql.
    """
    for key in ("PLATFORM_DB_URL", "REGISTRY_DB_URL", "DATABASE_URL"):
        url = os.environ.get(key, "").strip()
        if url:
            return url

    db_type = get_platform_db_type()
    host = os.environ.get("PLATFORM_DB_HOST", "localhost")
    port = int(os.environ.get("PLATFORM_DB_PORT", "3306" if db_type == "mysql" else "5432"))
    user = os.environ.get("PLATFORM_DB_USER", "postgres" if db_type == "postgresql" else "smartbook")
    password = os.environ.get(
        "PLATFORM_DB_PASSWORD",
        "postgres" if db_type == "postgresql" else "smartbook",
    )
    name = os.environ.get("PLATFORM_DB_NAME", "platform_registry")

    user_q = quote_plus(user)
    password_q = quote_plus(password)

    if db_type == "mysql":
        return f"mysql+aiomysql://{user_q}:{password_q}@{host}:{port}/{name}"
    return f"postgresql+asyncpg://{user_q}:{password_q}@{host}:{port}/{name}"


def platform_engine_connect_args() -> dict[str, Any]:
    """Driver-specific connect args for the platform DB engine."""
    if get_platform_db_type() == "mysql":
        return {"charset": "utf8mb4"}
    return {}


def resolve_platform_db_url_sync() -> str:
    """Sync SQLAlchemy URL (Alembic migrations)."""
    url = resolve_platform_db_url()
    return url.replace("+asyncpg", "").replace("+aiomysql", "+pymysql")


def resolve_shared_tenant_db_url() -> str:
    """
    Async URL for the shared multi-tenant accounting DB.

    Used when the JWT has no account_set_id yet (first Account Set create / list).
    Priority: SHARED_TENANT_DB_URL / TENANT_DB_URL, else same host as platform
    with database name ``smartbook_shared`` (mysql) or ``smartbook_shared`` (pg).
    """
    for key in ("SHARED_TENANT_DB_URL", "TENANT_DB_URL"):
        url = os.environ.get(key, "").strip()
        if url:
            return url

    db_type = get_platform_db_type()
    host = os.environ.get("PLATFORM_DB_HOST", "localhost")
    port = int(os.environ.get("PLATFORM_DB_PORT", "3306" if db_type == "mysql" else "5432"))
    user = os.environ.get("PLATFORM_DB_USER", "postgres" if db_type == "postgresql" else "smartbook")
    password = os.environ.get(
        "PLATFORM_DB_PASSWORD",
        "postgres" if db_type == "postgresql" else "smartbook",
    )
    name = os.environ.get("SHARED_TENANT_DB_NAME", "smartbook_shared")
    user_q = quote_plus(user)
    password_q = quote_plus(password)
    if db_type == "mysql":
        return f"mysql+aiomysql://{user_q}:{password_q}@{host}:{port}/{name}"
    return f"postgresql+asyncpg://{user_q}:{password_q}@{host}:{port}/{name}"
