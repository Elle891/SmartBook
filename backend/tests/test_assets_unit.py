"""
Unit tests for Fixed Asset module — depreciation, disposal, asset register.

_Requirements: 18.1–18.7 (Task 14.1)_
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from assets.calculations import (
    METHOD_DECLINING_BALANCE,
    METHOD_STRAIGHT_LINE,
    build_disposal_voucher_entries,
    calculate_depreciation_amount,
    declining_balance_monthly,
    disposal_gain_loss,
    straight_line_monthly,
)


class TestStraightLineDepreciation:
    def test_monthly_amount(self):
        amount = straight_line_monthly(Decimal("120000"), 60)
        assert amount == Decimal("2000.0000")

    def test_calculate_depreciation_amount(self):
        amount = calculate_depreciation_amount(
            cost=Decimal("120000"),
            net_book_value=Decimal("100000"),
            useful_life_months=60,
            method=METHOD_STRAIGHT_LINE,
        )
        assert amount == Decimal("2000.0000")


class TestDecliningBalanceDepreciation:
    def test_monthly_amount(self):
        amount = declining_balance_monthly(Decimal("100000"), Decimal("0.02"))
        assert amount == Decimal("2000.0000")

    def test_capped_at_net_book_value(self):
        amount = declining_balance_monthly(Decimal("100"), Decimal("1.5"))
        assert amount == Decimal("100.0000")

    def test_calculate_depreciation_amount(self):
        amount = calculate_depreciation_amount(
            cost=Decimal("120000"),
            net_book_value=Decimal("80000"),
            useful_life_months=60,
            method=METHOD_DECLINING_BALANCE,
            declining_balance_rate=Decimal("0.025"),
        )
        assert amount == Decimal("2000.0000")


class TestDisposalGainLoss:
    def test_gain(self):
        assert disposal_gain_loss(Decimal("5000"), Decimal("8000")) == Decimal("3000.00")

    def test_loss(self):
        assert disposal_gain_loss(Decimal("5000"), Decimal("3000")) == Decimal("-2000.00")

    def test_break_even(self):
        assert disposal_gain_loss(Decimal("5000"), Decimal("5000")) == Decimal("0.00")


class TestDisposalVoucher:
    def _assert_balanced(self, entries: list[dict]) -> None:
        debits = sum(e["debit_amount"] for e in entries)
        credits = sum(e["credit_amount"] for e in entries)
        assert debits == credits

    def test_disposal_with_gain_balances(self):
        entries = build_disposal_voucher_entries(
            cost=Decimal("10000"),
            accumulated_depreciation=Decimal("4000"),
            net_book_value=Decimal("6000"),
            proceeds=Decimal("8000"),
            asset_account="1601",
            accum_dep_account="1602",
            cash_account="1001",
            gain_account="5051",
            loss_account="6603",
        )
        self._assert_balanced(entries)
        assert any(e["account_code"] == "5051" for e in entries)

    def test_disposal_with_loss_balances(self):
        entries = build_disposal_voucher_entries(
            cost=Decimal("10000"),
            accumulated_depreciation=Decimal("4000"),
            net_book_value=Decimal("6000"),
            proceeds=Decimal("4000"),
            asset_account="1601",
            accum_dep_account="1602",
            cash_account="1001",
            gain_account="5051",
            loss_account="6603",
        )
        self._assert_balanced(entries)
        assert any(e["account_code"] == "6603" for e in entries)


class TestAssetRegister:
    @pytest.mark.asyncio
    async def test_register_returns_active_assets(self):
        from assets import service as asset_svc

        asset = MagicMock()
        asset.id = "a1"
        asset.name = "Laptop"
        asset.category = "IT"
        asset.acquisition_date = date(2024, 1, 1)
        asset.cost = 12000.0
        asset.accumulated_depreciation = 2000.0
        asset.net_book_value = 10000.0
        asset.depreciation_method = METHOD_STRAIGHT_LINE
        asset.is_disposed = False
        asset.disposed_at = None

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [asset]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result_mock)

        rows = await asset_svc.get_asset_register(db, account_set_id="as-1")
        assert len(rows) == 1
        assert rows[0]["name"] == "Laptop"
        assert rows[0]["net_book_value"] == 10000.0
        assert rows[0]["accumulated_depreciation"] == 2000.0


class TestConfirmDepreciation:
    @pytest.mark.asyncio
    async def test_confirm_updates_assets_and_creates_voucher(self):
        from assets import service as asset_svc

        preview = {
            "asset_count": 1,
            "lines": [
                {
                    "asset_id": "a1",
                    "depreciation_amount": 1000.0,
                }
            ],
        }
        asset = MagicMock()
        asset.id = "a1"
        asset.accumulated_depreciation = 0.0
        asset.net_book_value = 10000.0

        account_set = MagicMock()
        account_set.standard = "CAS"

        voucher = MagicMock()
        voucher.id = "v1"

        db = AsyncMock()
        execute_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=account_set)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=asset)),
        ]
        db.execute = AsyncMock(side_effect=execute_results)

        with (
            patch.object(asset_svc, "calculate_depreciation", AsyncMock(return_value=preview)),
            patch.object(asset_svc, "create_voucher", AsyncMock(return_value=voucher)),
        ):
            result = await asset_svc.confirm_depreciation(
                db,
                account_set_id="as-1",
                period_code="202501",
                user_id="u1",
            )

        assert result["voucher_id"] == "v1"
        assert result["total_depreciation"] == 1000.0
        assert asset.accumulated_depreciation == 1000.0
        assert asset.net_book_value == 9000.0


class TestDisposeAsset:
    @pytest.mark.asyncio
    async def test_dispose_already_disposed_raises(self):
        from fastapi import HTTPException

        from assets import service as asset_svc

        asset = MagicMock()
        asset.is_disposed = True

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = asset
        db.execute = AsyncMock(return_value=result_mock)

        with patch.object(asset_svc, "assert_period_open", AsyncMock()):
            with pytest.raises(HTTPException) as exc:
                await asset_svc.dispose_asset(
                    db,
                    account_set_id="as-1",
                    asset_id="a1",
                    disposal_date=date(2025, 1, 31),
                    proceeds_amount=5000.0,
                    period_code="202501",
                    user_id="u1",
                )
        assert exc.value.status_code == 409
