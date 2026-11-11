"""
Report data source registration and connection testing (Req 9.13–9.15).
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.report_engine import (
    MODE_API,
    MODE_DATA_SERVER,
    MODE_LEDGER,
    VENDOR_MYSQL,
    VENDOR_ORACLE,
    VENDOR_SQLSERVER,
    ReportDataSource,
)
from reports.errors import ReportValidationError

SUPPORTED_VENDORS = {VENDOR_MYSQL, VENDOR_ORACLE, VENDOR_SQLSERVER}


def _store_credentials(account_set_id: str, name: str, credentials: dict[str, Any]) -> str:
    """Store credentials in Vault; return reference path."""
    if os.getenv("ENVIRONMENT") == "test" or not os.getenv("VAULT_ADDR"):
        return f"test://report-ds/{account_set_id}/{name}"
    from platform.vault_client import get_vault_client

    ref = f"report-data-sources/{account_set_id}/{name}"
    client = get_vault_client()
    client.write_secret(ref, credentials)
    return ref


async def register_data_source(
    db: AsyncSession,
    *,
    account_set_id: str,
    name: str,
    connection_mode: str,
    vendor: str | None = None,
    endpoint_url: str | None = None,
    host: str | None = None,
    port: int | None = None,
    database_name: str | None = None,
    credentials: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> ReportDataSource:
    if connection_mode not in (MODE_LEDGER, MODE_API, MODE_DATA_SERVER):
        raise ReportValidationError(f"Unsupported connection mode: {connection_mode}")

    credentials_ref = None
    if connection_mode == MODE_API:
        if not endpoint_url:
            raise ReportValidationError("API data sources require endpoint_url.")
        if credentials:
            credentials_ref = _store_credentials(account_set_id, name, credentials)
    elif connection_mode == MODE_DATA_SERVER:
        if vendor not in SUPPORTED_VENDORS:
            raise ReportValidationError(
                f"Data Server vendor must be one of: {', '.join(sorted(SUPPORTED_VENDORS))}."
            )
        if not host or not database_name:
            raise ReportValidationError("Data Server requires host and database_name.")
        if credentials:
            credentials_ref = _store_credentials(account_set_id, name, credentials)

    source = ReportDataSource(
        account_set_id=account_set_id,
        name=name,
        connection_mode=connection_mode,
        vendor=vendor,
        endpoint_url=endpoint_url,
        host=host,
        port=port,
        database_name=database_name,
        credentials_ref=credentials_ref,
        config=config or {},
        status="Active",
    )
    db.add(source)
    await db.flush()
    return source


async def list_data_sources(
    db: AsyncSession,
    *,
    account_set_id: str,
) -> list[ReportDataSource]:
    result = await db.execute(
        select(ReportDataSource)
        .where(ReportDataSource.account_set_id == account_set_id)
        .order_by(ReportDataSource.name)
    )
    return list(result.scalars().all())


async def test_data_source_connection(
    db: AsyncSession,
    *,
    account_set_id: str,
    data_source_id: str,
) -> dict[str, Any]:
    result = await db.execute(
        select(ReportDataSource).where(
            ReportDataSource.id == data_source_id,
            ReportDataSource.account_set_id == account_set_id,
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found.")

    if source.connection_mode == MODE_LEDGER:
        return {"success": True, "message": "Ledger data source is always available."}

    if os.getenv("ENVIRONMENT") == "test" or os.getenv("REPORT_DS_TEST_MODE") == "stub":
        if source.connection_mode == MODE_DATA_SERVER and source.vendor not in SUPPORTED_VENDORS:
            source.status = "Failed"
            await db.flush()
            return {"success": False, "message": f"Unsupported vendor: {source.vendor}"}
        return {"success": True, "message": f"{source.connection_mode} connection OK (stub)."}

    if source.connection_mode == MODE_API:
        return {"success": False, "message": "Live API test requires configured OCR/tax services."}

    source.status = "Failed"
    await db.flush()
    return {"success": False, "message": "Live database connection test not configured in this environment."}
