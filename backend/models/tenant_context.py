"""
Tenant isolation helpers — PostgreSQL RLS session variables and query guards.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform.registry.models import DbType

logger = logging.getLogger(__name__)

_RLS_SETTING = "app.current_account_set_id"


async def apply_tenant_context(
    session: AsyncSession,
    account_set_id: str,
    db_type: DbType,
) -> None:
    """Set per-request tenant context for PostgreSQL RLS (no-op on MySQL/SQLite)."""
    if db_type != DbType.postgresql:
        return
    await session.execute(
        text(f"SELECT set_config('{_RLS_SETTING}', :asid, true)"),
        {"asid": str(account_set_id)},
    )
    logger.debug("RLS context set account_set_id=%s", account_set_id)


def require_account_set_filter(account_set_id: str | None) -> str:
    """Validate account_set_id is present for application-layer isolation (MySQL)."""
    if not account_set_id:
        raise ValueError("account_set_id is required for tenant-scoped queries")
    return account_set_id
