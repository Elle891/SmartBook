"""
Bank Integration service — connections, sync, balance, routing.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bank import cache, clients, notifications, routing, vault_store
from bank.errors import BankConnectionError, RoutingValidationError
from bank.retry import retry_with_backoff
from models.bank import BankConnection, BankTransaction, RoutingConfig
from voucher.service import write_tenant_audit

logger = logging.getLogger(__name__)

_connection_down: dict[str, bool] = {}


async def _get_connection(
    db: AsyncSession,
    *,
    account_set_id: str,
    connection_id: str,
) -> BankConnection:
    result = await db.execute(
        select(BankConnection).where(
            BankConnection.id == connection_id,
            BankConnection.account_set_id == account_set_id,
        )
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank connection not found.")
    return connection


async def _load_credentials(connection: BankConnection) -> dict[str, Any]:
    return vault_store.read_connection_credentials(connection.credentials_vault_path)


async def connect_bank(
    db: AsyncSession,
    *,
    account_set_id: str,
    bank_code: str,
    account_number: str,
    credentials: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    """Connect a bank account; credentials stored in Vault only (Req 2.2)."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Bank credentials are required.",
        )

    connection_id = str(uuid.uuid4())
    vault_path = vault_store.store_connection_credentials(
        account_set_id, connection_id, credentials
    )

    connection = BankConnection(
        id=uuid.UUID(connection_id),
        account_set_id=uuid.UUID(account_set_id),
        bank_code=bank_code.upper(),
        account_number=account_number,
        credentials_vault_path=vault_path,
        status="Active",
    )
    db.add(connection)
    await db.flush()

    verify = await verify_connection(db, account_set_id=account_set_id, connection_id=connection_id)
    if not verify.get("connected"):
        connection.status = "Inactive"
        await db.flush()
        raise BankConnectionError(
            verify.get("message", "Bank connection verification failed."),
        )

    await write_tenant_audit(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        action="bank.connect",
        entity_type="BankConnection",
        entity_id=connection_id,
        new_value={"bank_code": bank_code, "account_number": account_number},
    )

    return {
        "connection_id": connection_id,
        "bank_code": connection.bank_code,
        "account_number": connection.account_number,
        "status": connection.status,
        "credentials_vault_path": vault_path,
        "supported_routing_methods": routing.get_bank_supported_methods(connection.bank_code),
    }


async def verify_connection(
    db: AsyncSession,
    *,
    account_set_id: str,
    connection_id: str,
) -> dict[str, Any]:
    """Verify bank connection status (Req 2.3)."""
    connection = await _get_connection(db, account_set_id=account_set_id, connection_id=connection_id)
    credentials = await _load_credentials(connection)

    async def _op() -> dict[str, Any]:
        return await clients.verify_connection(
            bank_code=connection.bank_code,
            account_number=connection.account_number,
            credentials=credentials,
        )

    try:
        result = await retry_with_backoff(_op, operation_name="verify_connection")
    except Exception as exc:
        logger.error("Bank verify failed connection=%s: %s", connection_id, exc)
        _connection_down[connection_id] = True
        raise BankConnectionError(
            f"Unable to verify bank connection: {exc}",
            details={"connection_id": connection_id},
        ) from exc

    connected = bool(result.get("connected"))
    connection.status = "Active" if connected else "Inactive"
    if connected and _connection_down.pop(connection_id, False):
        notifications.notify_finance_users(
            account_set_id=account_set_id,
            event="connectivity_restored",
            message=f"Bank connectivity restored for {connection.bank_code}.",
            connection_id=connection_id,
        )
    await db.flush()
    return {
        "connection_id": connection_id,
        "connected": connected,
        "status": connection.status,
        "message": result.get("message", ""),
    }


async def sync_transactions(
    db: AsyncSession,
    *,
    account_set_id: str,
    connection_id: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Import bank transactions with deduplication (Req 3.1–3.4)."""
    connection = await _get_connection(db, account_set_id=account_set_id, connection_id=connection_id)
    credentials = await _load_credentials(connection)
    since = connection.last_synced_at

    async def _op() -> list[dict[str, Any]]:
        return await clients.fetch_transactions(
            bank_code=connection.bank_code,
            account_number=connection.account_number,
            credentials=credentials,
            since=since,
        )

    try:
        rows = await retry_with_backoff(_op, operation_name="sync_transactions")
    except Exception as exc:
        logger.error("Bank sync failed connection=%s: %s", connection_id, exc)
        _connection_down[connection_id] = True
        raise BankConnectionError(
            f"Transaction sync failed: {exc}",
            details={"connection_id": connection_id},
        ) from exc

    imported = 0
    skipped = 0
    inflow_total = 0.0
    outflow_total = 0.0

    for row in rows:
        txn_date = date.fromisoformat(str(row["date"]))
        amount = float(row["amount"])
        direction = str(row.get("direction", "Inflow"))
        reference = str(row.get("reference_number", ""))
        if direction == "Inflow":
            inflow_total += amount
        else:
            outflow_total += amount

        existing = await db.execute(
            select(BankTransaction.id).where(
                BankTransaction.account_set_id == account_set_id,
                BankTransaction.date == txn_date,
                BankTransaction.amount == amount,
                BankTransaction.reference_number == reference,
            )
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        txn = BankTransaction(
            account_set_id=uuid.UUID(account_set_id),
            connection_id=connection.id,
            date=txn_date,
            amount=amount,
            direction=direction,
            description=str(row.get("description", "")),
            reference_number=reference,
        )
        db.add(txn)
        await db.flush()
        imported += 1

    connection.last_synced_at = datetime.now(timezone.utc)
    if _connection_down.pop(connection_id, False):
        notifications.notify_finance_users(
            account_set_id=account_set_id,
            event="connectivity_restored",
            message=f"Bank sync resumed for {connection.bank_code}.",
            connection_id=connection_id,
        )
    await db.flush()

    if user_id:
        await write_tenant_audit(
            db,
            account_set_id=account_set_id,
            user_id=user_id,
            action="bank.sync",
            entity_type="BankConnection",
            entity_id=connection_id,
            new_value={"imported": imported, "skipped": skipped},
        )

    return {
        "connection_id": connection_id,
        "imported": imported,
        "skipped_duplicates": skipped,
        "net_cash_flow": inflow_total - outflow_total,
        "last_synced_at": connection.last_synced_at.isoformat() if connection.last_synced_at else None,
    }


async def get_balance(
    db: AsyncSession,
    *,
    account_set_id: str,
    connection_id: str,
    as_of: date | None = None,
    allow_stale: bool = True,
) -> dict[str, Any]:
    """Retrieve balance with 1-hour Redis cache; stale fallback on failure (Req 4.1–4.5)."""
    connection = await _get_connection(db, account_set_id=account_set_id, connection_id=connection_id)
    as_of_key = as_of.isoformat() if as_of else None

    cached = await cache.get_cached_balance(connection_id, as_of_key)
    if cached and not cached.get("stale"):
        return {**cached, "from_cache": True}

    credentials = await _load_credentials(connection)

    async def _op() -> dict[str, Any]:
        return await clients.fetch_balance(
            bank_code=connection.bank_code,
            account_number=connection.account_number,
            credentials=credentials,
            as_of=as_of,
        )

    try:
        live = await retry_with_backoff(_op, operation_name="get_balance")
        payload = {
            **live,
            "connection_id": connection_id,
            "currency": live.get("currency", "CNY"),
            "stale": False,
            "from_cache": False,
        }
        await cache.set_cached_balance(connection_id, payload, as_of=as_of_key)
        return payload
    except Exception as exc:
        logger.error("Balance retrieval failed connection=%s: %s", connection_id, exc)
        if cached and allow_stale:
            return {**cached, "stale": True, "from_cache": True}
        if allow_stale:
            stale = await cache.get_cached_balance(connection_id, as_of_key)
            if stale:
                return {**stale, "stale": True, "from_cache": True}
        raise BankConnectionError(
            f"Balance retrieval failed: {exc}",
            details={"connection_id": connection_id},
        ) from exc


async def configure_routing_method(
    db: AsyncSession,
    *,
    account_set_id: str,
    connection_id: str,
    routing_method: str,
    params: dict[str, Any],
    is_default: bool,
    user_id: str,
) -> dict[str, Any]:
    """Configure routing method; params stored in Vault (Req 25.3–25.7, 25.9)."""
    connection = await _get_connection(db, account_set_id=account_set_id, connection_id=connection_id)
    supported = routing.get_bank_supported_methods(connection.bank_code)
    if routing_method not in supported:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": f"Routing method {routing_method} is not supported for {connection.bank_code}.",
                "supported_methods": supported,
            },
        )

    try:
        routing.validate_routing_params(routing_method, params)
    except RoutingValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.to_dict(),
        ) from exc

    vault_path = routing.routing_vault_path(connection_id, routing_method)
    vault_store.store_routing_params(vault_path, params)

    result = await db.execute(
        select(RoutingConfig).where(
            RoutingConfig.connection_id == connection_id,
            RoutingConfig.routing_method == routing_method,
        )
    )
    config = result.scalar_one_or_none()
    old_value = None
    if config is None:
        config = RoutingConfig(
            connection_id=uuid.UUID(connection_id),
            routing_method=routing_method,
            params_vault_path=vault_path,
            is_default=is_default,
            is_available=True,
        )
        db.add(config)
    else:
        old_value = {"params_vault_path": config.params_vault_path, "is_default": config.is_default}
        config.params_vault_path = vault_path
        config.is_default = is_default
        config.is_available = True

    if is_default:
        others = await db.execute(
            select(RoutingConfig).where(
                RoutingConfig.connection_id == connection_id,
                RoutingConfig.routing_method != routing_method,
            )
        )
        for other in others.scalars():
            other.is_default = False

    await db.flush()

    await write_tenant_audit(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        action="bank.configure_routing",
        entity_type="RoutingConfig",
        entity_id=str(config.id),
        old_value=old_value,
        new_value={"routing_method": routing_method, "is_default": is_default},
    )

    return {
        "config_id": str(config.id),
        "connection_id": connection_id,
        "routing_method": routing_method,
        "params_vault_path": vault_path,
        "is_default": config.is_default,
        "is_available": config.is_available,
    }


async def get_available_routing_methods(
    db: AsyncSession,
    *,
    account_set_id: str,
    connection_id: str,
) -> dict[str, Any]:
    """Return configured and available routing methods (Req 25.2, Property 22)."""
    connection = await _get_connection(db, account_set_id=account_set_id, connection_id=connection_id)
    bank_supported = set(routing.get_bank_supported_methods(connection.bank_code))

    result = await db.execute(
        select(RoutingConfig).where(
            RoutingConfig.connection_id == connection_id,
            RoutingConfig.is_available.is_(True),
        )
    )
    configured = [c.routing_method for c in result.scalars() if c.routing_method in bank_supported]
    return {
        "connection_id": connection_id,
        "bank_supported": sorted(bank_supported),
        "available_methods": sorted(set(configured)),
    }


async def set_default_routing_method(
    db: AsyncSession,
    *,
    account_set_id: str,
    connection_id: str,
    routing_method: str,
    user_id: str,
) -> dict[str, Any]:
    connection = await _get_connection(db, account_set_id=account_set_id, connection_id=connection_id)
    result = await db.execute(
        select(RoutingConfig).where(
            RoutingConfig.connection_id == connection_id,
            RoutingConfig.routing_method == routing_method,
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routing config not found.")

    others = await db.execute(
        select(RoutingConfig).where(RoutingConfig.connection_id == connection_id)
    )
    for other in others.scalars():
        other.is_default = other.id == config.id
    config.is_default = True
    await db.flush()

    await write_tenant_audit(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        action="bank.set_default_routing",
        entity_type="RoutingConfig",
        entity_id=str(config.id),
        new_value={"routing_method": routing_method},
    )
    return {
        "config_id": str(config.id),
        "connection_id": connection_id,
        "routing_method": routing_method,
        "is_default": True,
    }


async def get_routing_config(
    db: AsyncSession,
    *,
    account_set_id: str,
    connection_id: str,
) -> list[dict[str, Any]]:
    await _get_connection(db, account_set_id=account_set_id, connection_id=connection_id)
    result = await db.execute(
        select(RoutingConfig).where(RoutingConfig.connection_id == connection_id)
    )
    return [
        {
            "config_id": str(c.id),
            "connection_id": connection_id,
            "routing_method": c.routing_method,
            "params_vault_path": c.params_vault_path,
            "is_default": c.is_default,
            "is_available": c.is_available,
        }
        for c in result.scalars()
    ]


async def mark_routing_method_unavailable(
    db: AsyncSession,
    *,
    account_set_id: str,
    connection_id: str,
    routing_method: str,
    reason: str,
    user_id: str,
) -> dict[str, Any]:
    """Mark routing channel unavailable and notify Finance_User (Req 25.8)."""
    await _get_connection(db, account_set_id=account_set_id, connection_id=connection_id)
    result = await db.execute(
        select(RoutingConfig).where(
            RoutingConfig.connection_id == connection_id,
            RoutingConfig.routing_method == routing_method,
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routing config not found.")

    config.is_available = False
    if config.is_default:
        config.is_default = False
    await db.flush()

    notifications.notify_finance_users(
        account_set_id=account_set_id,
        event="routing_unavailable",
        message=f"Routing method {routing_method} is temporarily unavailable: {reason}",
        connection_id=connection_id,
    )

    await write_tenant_audit(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        action="bank.routing_unavailable",
        entity_type="RoutingConfig",
        entity_id=str(config.id),
        new_value={"routing_method": routing_method, "reason": reason},
    )

    return {
        "config_id": str(config.id),
        "routing_method": routing_method,
        "is_available": False,
        "reason": reason,
    }


async def list_connections(
    db: AsyncSession,
    *,
    account_set_id: str,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(BankConnection).where(BankConnection.account_set_id == account_set_id)
    )
    return [
        {
            "connection_id": str(c.id),
            "bank_code": c.bank_code,
            "account_number": c.account_number,
            "status": c.status,
            "last_synced_at": c.last_synced_at.isoformat() if c.last_synced_at else None,
        }
        for c in result.scalars()
    ]


async def sync_all_connections(
    db: AsyncSession,
    *,
    account_set_id: str,
) -> dict[str, Any]:
    """Sync all active connections for an account set (Celery beat / scheduled)."""
    result = await db.execute(
        select(BankConnection).where(
            BankConnection.account_set_id == account_set_id,
            BankConnection.status == "Active",
        )
    )
    connections = list(result.scalars())
    results = []
    for connection in connections:
        try:
            sync_result = await sync_transactions(
                db,
                account_set_id=account_set_id,
                connection_id=str(connection.id),
            )
            results.append(sync_result)
        except BankConnectionError as exc:
            logger.warning("Scheduled sync skipped connection=%s: %s", connection.id, exc.message)
            results.append({"connection_id": str(connection.id), "error": exc.message})
    return {"account_set_id": account_set_id, "results": results}
