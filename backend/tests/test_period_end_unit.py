"""
Unit tests for Period-End Processor — close pre-flight and balance carry-forward.

_Requirements: 15.4, 15.5, 15.6, 15.7 (Task 11.2)_
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from period_end.accounts import (
    CARRY_RETAINED_EARNINGS,
    UnapprovedVouchersError,
    get_carry_forward_account,
)
from period_end.periods import next_period_code
from period_end.service import close_period


class TestCarryForwardAccounts:
    def test_cas_retained_earnings_is_3141(self):
        assert get_carry_forward_account("CAS", CARRY_RETAINED_EARNINGS) == "3141"

    def test_ifrs_retained_earnings_is_3300(self):
        assert get_carry_forward_account("IFRS", CARRY_RETAINED_EARNINGS) == "3300"


class TestNextPeriodCode:
    def test_advances_month(self):
        assert next_period_code("202501") == "202502"

    def test_rolls_year(self):
        assert next_period_code("202512") == "202601"


class TestClosePeriod:
    @pytest.mark.asyncio
    async def test_rejects_when_unapproved_vouchers_exist(self):
        from period_end import service as pe_svc

        db = AsyncMock()
        with patch.object(pe_svc, "_count_unapproved_vouchers", AsyncMock(return_value=3)):
            with pytest.raises(UnapprovedVouchersError) as exc:
                await close_period(
                    db,
                    account_set_id=str(uuid.uuid4()),
                    period_code="202501",
                    user_id="user-1",
                )
        assert exc.value.count == 3

    @pytest.mark.asyncio
    async def test_carries_balance_sheet_closing_to_next_period_opening(self):
        from period_end import service as pe_svc

        account_set_id = str(uuid.uuid4())
        period_code = "202501"
        next_code = "202502"

        balance = MagicMock()
        balance.account_code = "1001"
        balance.closing_balance = 5000.0
        balance.opening_balance = 1000.0

        account = MagicMock()
        account.name = "Cash"
        account.account_type = "Asset"

        period = MagicMock()
        period.is_closed = False
        period.closed_at = None

        db = AsyncMock()
        db.flush = AsyncMock()

        with (
            patch.object(pe_svc, "_count_unapproved_vouchers", AsyncMock(return_value=0)),
            patch.object(pe_svc, "ensure_period_row", AsyncMock(return_value=period)),
            patch.object(
                pe_svc,
                "_balances_with_types",
                AsyncMock(return_value=[(balance, account)]),
            ),
            patch.object(pe_svc, "close_period_row", AsyncMock()),
        ):
            next_balance_result = MagicMock()
            next_balance_result.scalar_one_or_none.return_value = None
            db.execute = AsyncMock(return_value=next_balance_result)

            result = await close_period(
                db,
                account_set_id=account_set_id,
                period_code=period_code,
                user_id="user-1",
            )

        assert result["next_period_code"] == next_code
        assert result["accounts_carried"] == 1
        added = db.add.call_args[0][0]
        assert added.period_code == next_code
        assert added.opening_balance == 5000.0


class TestClosedPeriodVoucherGuard:
    @pytest.mark.asyncio
    async def test_create_voucher_rejects_closed_period(self):
        from voucher.service import create_voucher

        db = AsyncMock()
        with patch("period_end.periods.is_period_closed", AsyncMock(return_value=True)):
            with pytest.raises(HTTPException) as exc:
                await create_voucher(
                    db,
                    account_set_id=str(uuid.uuid4()),
                    period_code="202501",
                    voucher_type="Receipt",
                    voucher_date=__import__("datetime").date.today(),
                    entries=[
                        {"account_code": "1001", "debit_amount": 10, "credit_amount": 0},
                        {"account_code": "2001", "debit_amount": 0, "credit_amount": 10},
                    ],
                    attachments=[],
                    created_by_user_id=str(uuid.uuid4()),
                )
        assert exc.value.status_code == 422
        assert "closed" in exc.value.detail.lower()
