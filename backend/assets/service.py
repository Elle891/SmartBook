"""
Fixed Asset module service.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assets.calculations import (
    METHOD_DECLINING_BALANCE,
    METHOD_STRAIGHT_LINE,
    build_disposal_voucher_entries,
    calculate_depreciation_amount,
    disposal_gain_loss,
    to_decimal,
)
from models.account_set import AccountSet
from models.assets import FixedAsset
from period_end.accounts import (
    CARRY_ACCUMULATED_DEPRECIATION,
    CARRY_DEPRECIATION_EXPENSE,
    get_carry_forward_account,
)
from period_end.periods import assert_period_open
from voucher.service import create_voucher

logger = logging.getLogger(__name__)

# CAS disposal accounts (simplified)
ASSET_ACCOUNT = "1601"
CASH_ACCOUNT = "1001"
GAIN_ON_DISPOSAL = "5051"
LOSS_ON_DISPOSAL = "6603"


async def register_asset(
    db: AsyncSession,
    *,
    account_set_id: str,
    name: str,
    category: str,
    acquisition_date: date,
    cost: float,
    useful_life_months: int,
    depreciation_method: str = METHOD_STRAIGHT_LINE,
    declining_balance_rate: float | None = None,
) -> FixedAsset:
    """Register a fixed asset (Req 18.1)."""
    if depreciation_method not in (METHOD_STRAIGHT_LINE, METHOD_DECLINING_BALANCE):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="depreciation_method must be StraightLine or DecliningBalance.",
        )
    if useful_life_months < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="useful_life_months must be at least 1.",
        )
    if depreciation_method == METHOD_DECLINING_BALANCE and declining_balance_rate is None:
        declining_balance_rate = 2.0 / useful_life_months

    asset = FixedAsset(
        account_set_id=account_set_id,
        name=name,
        category=category,
        acquisition_date=acquisition_date,
        cost=cost,
        useful_life_months=useful_life_months,
        depreciation_method=depreciation_method,
        declining_balance_rate=declining_balance_rate,
        accumulated_depreciation=0,
        net_book_value=cost,
        is_disposed=False,
    )
    db.add(asset)
    await db.flush()
    return asset


async def get_asset_register(
    db: AsyncSession,
    *,
    account_set_id: str,
    include_disposed: bool = False,
) -> list[dict[str, Any]]:
    """Asset register with cost, accumulated depreciation, NBV (Req 18.6)."""
    stmt = select(FixedAsset).where(FixedAsset.account_set_id == account_set_id)
    if not include_disposed:
        stmt = stmt.where(FixedAsset.is_disposed.is_(False))
    stmt = stmt.order_by(FixedAsset.category, FixedAsset.name)
    result = await db.execute(stmt)
    assets = list(result.scalars().all())

    return [
        {
            "id": str(a.id),
            "name": a.name,
            "category": a.category,
            "acquisition_date": a.acquisition_date.isoformat(),
            "cost": float(a.cost),
            "accumulated_depreciation": float(a.accumulated_depreciation),
            "net_book_value": float(a.net_book_value),
            "depreciation_method": a.depreciation_method,
            "is_disposed": a.is_disposed,
            "disposed_at": a.disposed_at.isoformat() if a.disposed_at else None,
        }
        for a in assets
    ]


def _depreciation_for_asset(asset: FixedAsset) -> Decimal:
    rate = (
        to_decimal(asset.declining_balance_rate)
        if asset.declining_balance_rate is not None
        else None
    )
    return calculate_depreciation_amount(
        cost=to_decimal(asset.cost),
        net_book_value=to_decimal(asset.net_book_value),
        useful_life_months=asset.useful_life_months,
        method=asset.depreciation_method,
        declining_balance_rate=rate,
    )


async def calculate_depreciation(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
) -> dict[str, Any]:
    """Preview depreciation per active asset (Req 18.3) — does not persist."""
    await assert_period_open(db, account_set_id, period_code)

    result = await db.execute(
        select(FixedAsset).where(
            FixedAsset.account_set_id == account_set_id,
            FixedAsset.is_disposed.is_(False),
            FixedAsset.net_book_value > 0,
        )
    )
    assets = list(result.scalars().all())

    lines: list[dict[str, Any]] = []
    total = Decimal("0")
    for asset in assets:
        amount = _depreciation_for_asset(asset)
        if amount <= 0:
            continue
        lines.append(
            {
                "asset_id": str(asset.id),
                "name": asset.name,
                "depreciation_method": asset.depreciation_method,
                "depreciation_amount": float(amount),
                "current_net_book_value": float(asset.net_book_value),
                "projected_net_book_value": float(
                    max(to_decimal(asset.net_book_value) - amount, Decimal("0"))
                ),
            }
        )
        total += amount

    return {
        "period_code": period_code,
        "asset_count": len(lines),
        "total_depreciation": float(total),
        "lines": lines,
    }


async def confirm_depreciation(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    user_id: str,
    voucher_date: date | None = None,
) -> dict[str, Any]:
    """Apply depreciation to assets and create voucher (Req 18.4, 18.5)."""
    preview = await calculate_depreciation(
        db, account_set_id=account_set_id, period_code=period_code
    )
    if preview["asset_count"] == 0:
        return {
            "message": "No depreciation to record.",
            "voucher_id": None,
            "total_depreciation": 0.0,
        }

    account_set_result = await db.execute(
        select(AccountSet).where(AccountSet.id == account_set_id)
    )
    account_set = account_set_result.scalar_one_or_none()
    if account_set is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account set not found.")

    expense_code = get_carry_forward_account(
        account_set.standard, CARRY_DEPRECIATION_EXPENSE
    )
    accum_code = get_carry_forward_account(
        account_set.standard, CARRY_ACCUMULATED_DEPRECIATION
    )

    total_dep = Decimal("0")
    updated_assets: list[str] = []

    for line in preview["lines"]:
        asset_result = await db.execute(
            select(FixedAsset).where(FixedAsset.id == line["asset_id"])
        )
        asset = asset_result.scalar_one_or_none()
        if asset is None:
            continue
        amount = to_decimal(line["depreciation_amount"])
        asset.accumulated_depreciation = float(
            to_decimal(asset.accumulated_depreciation) + amount
        )
        asset.net_book_value = float(
            max(to_decimal(asset.net_book_value) - amount, Decimal("0"))
        )
        total_dep += amount
        updated_assets.append(str(asset.id))

    entries = [
        {
            "account_code": expense_code,
            "debit_amount": float(total_dep),
            "credit_amount": 0,
            "description": f"Depreciation — {period_code}",
        },
        {
            "account_code": accum_code,
            "debit_amount": 0,
            "credit_amount": float(total_dep),
            "description": f"Accumulated depreciation — {period_code}",
        },
    ]

    vdate = voucher_date or date.today()
    voucher = await create_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_type="Transfer",
        voucher_date=vdate,
        entries=entries,
        attachments=[],
        created_by_user_id=user_id,
    )
    await db.flush()

    return {
        "message": "Depreciation confirmed and voucher created.",
        "voucher_id": str(voucher.id),
        "period_code": period_code,
        "total_depreciation": float(total_dep),
        "assets_updated": updated_assets,
    }


async def dispose_asset(
    db: AsyncSession,
    *,
    account_set_id: str,
    asset_id: str,
    disposal_date: date,
    proceeds_amount: float,
    period_code: str,
    user_id: str,
) -> dict[str, Any]:
    """Dispose asset with gain/loss calculation and voucher (Req 18.7)."""
    await assert_period_open(db, account_set_id, period_code)

    result = await db.execute(
        select(FixedAsset).where(
            FixedAsset.id == asset_id,
            FixedAsset.account_set_id == account_set_id,
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    if asset.is_disposed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Asset is already disposed.",
        )

    account_set_result = await db.execute(
        select(AccountSet).where(AccountSet.id == account_set_id)
    )
    account_set = account_set_result.scalar_one_or_none()
    if account_set is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account set not found.")

    cost = to_decimal(asset.cost)
    accum = to_decimal(asset.accumulated_depreciation)
    nbv = to_decimal(asset.net_book_value)
    proceeds = to_decimal(proceeds_amount)
    gain_loss = disposal_gain_loss(nbv, proceeds)

    accum_code = get_carry_forward_account(
        account_set.standard, CARRY_ACCUMULATED_DEPRECIATION
    )

    entries = build_disposal_voucher_entries(
        cost=cost,
        accumulated_depreciation=accum,
        net_book_value=nbv,
        proceeds=proceeds,
        asset_account=ASSET_ACCOUNT,
        accum_dep_account=accum_code,
        cash_account=CASH_ACCOUNT,
        gain_account=GAIN_ON_DISPOSAL,
        loss_account=LOSS_ON_DISPOSAL,
    )

    voucher = await create_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_type="Transfer",
        voucher_date=disposal_date,
        entries=entries,
        attachments=[],
        created_by_user_id=user_id,
    )

    asset.is_disposed = True
    asset.disposed_at = disposal_date
    asset.net_book_value = 0
    await db.flush()

    return {
        "message": "Asset disposed and voucher created.",
        "asset_id": str(asset.id),
        "voucher_id": str(voucher.id),
        "proceeds_amount": float(proceeds),
        "net_book_value_at_disposal": float(nbv),
        "gain_or_loss": float(gain_loss),
        "is_gain": gain_loss > 0,
    }
