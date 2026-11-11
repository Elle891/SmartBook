"""
Audit log service — write and query audit records.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from audit.models import AuditLog

logger = logging.getLogger(__name__)


async def write_audit(
    session: AsyncSession,
    *,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    ip_address: str | None = None,
    account_set_id: str | None = None,
) -> Any:
    """Append an immutable audit record.

    When *account_set_id* is set, write a tenant ``audit_logs`` row
    (``TenantAuditLog``). Otherwise write a platform auth audit row.
    """
    if account_set_id:
        from models.tenant_audit import TenantAuditLog

        entry: Any = TenantAuditLog(
            account_set_id=account_set_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
        )
    else:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
        )
    session.add(entry)
    await session.flush()
    logger.debug(
        "Audit: user=%s action=%s entity=%s/%s account_set=%s",
        user_id,
        action,
        entity_type,
        entity_id,
        account_set_id or "",
    )
    return entry


async def get_audit_log(
    session: AsyncSession,
    *,
    account_set_id: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = 100,
) -> list[AuditLog]:
    """Query audit records (caller must enforce RBAC)."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)

    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)

    result = await session.execute(stmt)
    return list(result.scalars().all())
