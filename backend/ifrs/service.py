"""
IFRS Compliance service — fair value, leases, revenue, impairment, validation.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assets.service import register_asset
from ifrs.validation import ValidationResult, validate_ifrs_transaction
from ifrs.vouchers import (
    build_fair_value_entries,
    build_impairment_entries,
    build_revenue_recognition_entries,
    build_rou_initial_recognition_entries,
)
from models.account_set import AccountSet
from models.assets import FixedAsset
from models.reports import (
    IFRSFairValueAdjustment,
    IFRSLeaseContract,
    IFRSPerformanceObligation,
)
from period_end.periods import assert_period_open
from reports.errors import StandardMismatchError
from reports.terminology import STANDARD_IFRS
from voucher.service import create_voucher

logger = logging.getLogger(__name__)


async def _require_ifrs(db: AsyncSession, account_set_id: str) -> AccountSet:
    result = await db.execute(select(AccountSet).where(AccountSet.id == account_set_id))
    account_set = result.scalar_one_or_none()
    if account_set is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account set not found.")
    if account_set.standard != STANDARD_IFRS:
        raise StandardMismatchError(
            f"Operation requires an IFRS account set; this set uses {account_set.standard}."
        )
    return account_set


async def record_fair_value_adjustment(
    db: AsyncSession,
    *,
    account_set_id: str,
    account_code: str,
    period_code: str,
    carrying_amount: float,
    fair_value: float,
    voucher_date: date,
    user_id: str,
) -> dict[str, Any]:
    """IFRS 9 fair value adjustment with balanced voucher (Req 22.1)."""
    await _require_ifrs(db, account_set_id)
    await assert_period_open(db, account_set_id, period_code)

    adjustment = float(
        (Decimal(str(fair_value)) - Decimal(str(carrying_amount))).quantize(Decimal("0.01"))
    )
    if adjustment == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fair value equals carrying amount; no adjustment required.",
        )

    entries = build_fair_value_entries(
        account_code=account_code, adjustment_amount=adjustment
    )
    validation = validate_ifrs_transaction(entries)
    if not validation.valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=validation.to_dict())

    voucher = await create_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_type="Transfer",
        voucher_date=voucher_date,
        entries=entries,
        attachments=[],
        created_by_user_id=user_id,
    )

    record = IFRSFairValueAdjustment(
        account_set_id=account_set_id,
        account_code=account_code,
        period_code=period_code,
        carrying_amount=carrying_amount,
        fair_value=fair_value,
        adjustment_amount=adjustment,
        voucher_id=voucher.id,
    )
    db.add(record)
    await db.flush()

    return {
        "adjustment_id": str(record.id),
        "voucher_id": str(voucher.id),
        "adjustment_amount": adjustment,
    }


async def register_right_of_use_asset(
    db: AsyncSession,
    *,
    account_set_id: str,
    name: str,
    lease_term_months: int,
    lease_liability: float,
    rou_asset_value: float,
    commencement_date: date,
    period_code: str,
    user_id: str,
) -> dict[str, Any]:
    """IFRS 16 ROU asset + lease liability initial recognition (Req 22.2, 22.3)."""
    await _require_ifrs(db, account_set_id)
    if lease_term_months < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="lease_term_months must be at least 1.",
        )
    if lease_liability <= 0 or rou_asset_value <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="lease_liability and rou_asset_value must be positive.",
        )
    await assert_period_open(db, account_set_id, period_code)

    amount = min(lease_liability, rou_asset_value)
    entries = build_rou_initial_recognition_entries(amount=amount)
    voucher = await create_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_type="Transfer",
        voucher_date=commencement_date,
        entries=entries,
        attachments=[],
        created_by_user_id=user_id,
    )

    asset = await register_asset(
        db,
        account_set_id=account_set_id,
        name=name,
        category="Right-of-use",
        acquisition_date=commencement_date,
        cost=amount,
        useful_life_months=lease_term_months,
        depreciation_method="StraightLine",
    )

    lease = IFRSLeaseContract(
        account_set_id=account_set_id,
        asset_id=asset.id,
        lease_term_months=lease_term_months,
        lease_liability=amount,
        rou_asset_value=amount,
        commencement_date=commencement_date,
    )
    db.add(lease)
    await db.flush()

    return {
        "asset_id": str(asset.id),
        "lease_contract_id": str(lease.id),
        "voucher_id": str(voucher.id),
        "recognized_amount": amount,
    }


async def recognize_revenue(
    db: AsyncSession,
    *,
    account_set_id: str,
    obligation_id: str,
    amount: float,
    period_code: str,
    voucher_date: date,
    user_id: str,
) -> dict[str, Any]:
    """IFRS 15 revenue against performance obligation (Req 22.4)."""
    await _require_ifrs(db, account_set_id)
    await assert_period_open(db, account_set_id, period_code)

    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Recognition amount must be positive.",
        )

    result = await db.execute(
        select(IFRSPerformanceObligation).where(IFRSPerformanceObligation.id == obligation_id)
    )
    obligation = result.scalar_one_or_none()
    if obligation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Performance obligation not found.")

    new_total = float(obligation.recognized_to_date) + amount
    if new_total > float(obligation.allocated_value) + 0.0001:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Recognition exceeds allocated obligation value (IFRS 15).",
                "standard_reference": "IFRS 15",
                "allocated_value": float(obligation.allocated_value),
                "recognized_to_date": float(obligation.recognized_to_date),
            },
        )

    description = f"IFRS 15 revenue — {obligation.description}"
    entries = build_revenue_recognition_entries(amount=amount, description=description)
    voucher = await create_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_type="Receipt",
        voucher_date=voucher_date,
        entries=entries,
        attachments=[],
        created_by_user_id=user_id,
    )

    obligation.recognized_to_date = new_total
    if new_total >= float(obligation.allocated_value):
        obligation.is_satisfied = True
    await db.flush()

    return {
        "obligation_id": str(obligation.id),
        "voucher_id": str(voucher.id),
        "recognized_amount": amount,
        "recognized_to_date": new_total,
    }


async def perform_impairment_test(
    db: AsyncSession,
    *,
    account_set_id: str,
    asset_id: str,
    recoverable_amount: float,
    period_code: str,
    voucher_date: date,
    user_id: str,
) -> dict[str, Any]:
    """IAS 36 impairment when carrying > recoverable (Req 22.5)."""
    await _require_ifrs(db, account_set_id)
    await assert_period_open(db, account_set_id, period_code)

    if recoverable_amount < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="recoverable_amount must be non-negative.",
        )

    result = await db.execute(
        select(FixedAsset).where(
            FixedAsset.id == asset_id,
            FixedAsset.account_set_id == account_set_id,
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    carrying = float(asset.net_book_value)
    if carrying <= recoverable_amount:
        return {
            "asset_id": str(asset.id),
            "impairment_required": False,
            "voucher_id": None,
            "carrying_amount": carrying,
            "recoverable_amount": recoverable_amount,
        }

    loss = float(
        (Decimal(str(carrying)) - Decimal(str(recoverable_amount))).quantize(Decimal("0.01"))
    )
    entries = build_impairment_entries(loss_amount=loss, asset_account=str(asset.id))
    voucher = await create_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_type="Transfer",
        voucher_date=voucher_date,
        entries=entries,
        attachments=[],
        created_by_user_id=user_id,
    )

    asset.net_book_value = recoverable_amount
    await db.flush()

    return {
        "asset_id": str(asset.id),
        "impairment_required": True,
        "voucher_id": str(voucher.id),
        "impairment_loss": loss,
        "carrying_amount": carrying,
        "recoverable_amount": recoverable_amount,
    }


async def validate_ifrs_transaction_for_account_set(
    db: AsyncSession,
    *,
    account_set_id: str,
    entries: list[dict[str, Any]],
) -> ValidationResult:
    """Validate voucher entries on an IFRS account set (Req 22.7)."""
    await _require_ifrs(db, account_set_id)
    return validate_ifrs_transaction(entries)
