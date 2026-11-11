"""
ISO 20022 Payment Field Configuration service (Task 25).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.payment import PaymentFieldConfig
from payment.fields import (
    VISIBILITY_HIDDEN,
    VISIBILITY_OPTIONAL,
    VISIBILITY_REQUIRED,
    FieldConfigValidationError,
    build_default_field_configs,
    enforce_mandatory_fields,
    merge_with_mandatory_defaults,
    render_form_fields,
)
from voucher.service import write_tenant_audit


def _serialize(row: PaymentFieldConfig) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "account_set_id": str(row.account_set_id),
        "routing_method": row.routing_method,
        "settlement_method": row.settlement_method,
        "field_name": row.field_name,
        "visibility": row.visibility,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def get_field_configuration(
    db: AsyncSession,
    *,
    account_set_id: str,
    routing_method: str,
    settlement_method: str,
) -> dict[str, Any]:
    result = await db.execute(
        select(PaymentFieldConfig).where(
            PaymentFieldConfig.account_set_id == account_set_id,
            PaymentFieldConfig.routing_method == routing_method,
            PaymentFieldConfig.settlement_method == settlement_method,
        )
    )
    rows = list(result.scalars())
    if not rows:
        await seed_default_field_configs(db, account_set_id=account_set_id)
        result = await db.execute(
            select(PaymentFieldConfig).where(
                PaymentFieldConfig.account_set_id == account_set_id,
                PaymentFieldConfig.routing_method == routing_method,
                PaymentFieldConfig.settlement_method == settlement_method,
            )
        )
        rows = list(result.scalars())

    configs = {row.field_name: row.visibility for row in rows}
    configs = merge_with_mandatory_defaults(configs)
    return {
        "routing_method": routing_method,
        "settlement_method": settlement_method,
        "fields": [_serialize(r) for r in rows],
        "form_fields": render_form_fields(configs),
        "config_map": configs,
    }


async def save_field_configuration(
    db: AsyncSession,
    *,
    account_set_id: str,
    routing_method: str,
    settlement_method: str,
    field_configs: list[dict[str, str]],
    user_id: str,
) -> dict[str, Any]:
    """Admin-only save with mandatory field guard and audit (Req 28.7–28.8)."""
    config_map = {item["field_name"]: item["visibility"] for item in field_configs}
    try:
        enforce_mandatory_fields(config_map)
    except FieldConfigValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc

    config_map = merge_with_mandatory_defaults(config_map)
    old_rows = await db.execute(
        select(PaymentFieldConfig).where(
            PaymentFieldConfig.account_set_id == account_set_id,
            PaymentFieldConfig.routing_method == routing_method,
            PaymentFieldConfig.settlement_method == settlement_method,
        )
    )
    old_value = {r.field_name: r.visibility for r in old_rows.scalars()}

    for field_name, visibility in config_map.items():
        if visibility not in (VISIBILITY_REQUIRED, VISIBILITY_OPTIONAL, VISIBILITY_HIDDEN):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid visibility for {field_name}.",
            )
        result = await db.execute(
            select(PaymentFieldConfig).where(
                PaymentFieldConfig.account_set_id == account_set_id,
                PaymentFieldConfig.routing_method == routing_method,
                PaymentFieldConfig.settlement_method == settlement_method,
                PaymentFieldConfig.field_name == field_name,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = PaymentFieldConfig(
                account_set_id=uuid.UUID(account_set_id),
                routing_method=routing_method,
                settlement_method=settlement_method,
                field_name=field_name,
                visibility=visibility,
            )
            db.add(row)
        else:
            row.visibility = visibility

    await db.flush()

    await write_tenant_audit(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        action="payment_field_config.save",
        entity_type="PaymentFieldConfig",
        entity_id=f"{routing_method}/{settlement_method}",
        old_value=old_value or None,
        new_value=config_map,
    )

    return await get_field_configuration(
        db,
        account_set_id=account_set_id,
        routing_method=routing_method,
        settlement_method=settlement_method,
    )


async def seed_default_field_configs(
    db: AsyncSession,
    *,
    account_set_id: str,
) -> int:
    """Seed default ISO 20022 configs for all routing/settlement pairs."""
    created = 0
    for scope, routing, settlement, field_name, visibility in build_default_field_configs():
        _ = scope  # scope stored implicitly via routing/settlement matrix
        existing = await db.execute(
            select(PaymentFieldConfig.id).where(
                PaymentFieldConfig.account_set_id == account_set_id,
                PaymentFieldConfig.routing_method == routing,
                PaymentFieldConfig.settlement_method == settlement,
                PaymentFieldConfig.field_name == field_name,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        db.add(
            PaymentFieldConfig(
                account_set_id=uuid.UUID(account_set_id),
                routing_method=routing,
                settlement_method=settlement,
                field_name=field_name,
                visibility=visibility,
            )
        )
        created += 1
    if created:
        await db.flush()
    return created
