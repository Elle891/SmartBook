"""
Unit tests for IFRS Compliance service — standard guard and validation API.

_Requirements: 22.1–22.7 (Task 20)_
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from ifrs.validation import validate_ifrs_transaction
from ifrs.vouchers import build_fair_value_entries, entries_balanced
from reports.errors import StandardMismatchError
from reports.terminology import STANDARD_CAS, STANDARD_IFRS


class TestFairValueVoucherBuilder:
    def test_positive_adjustment_balances(self):
        entries = build_fair_value_entries(
            account_code="1510", adjustment_amount=500.0
        )
        assert entries_balanced(entries)

    def test_negative_adjustment_balances(self):
        entries = build_fair_value_entries(
            account_code="1510", adjustment_amount=-300.0
        )
        assert entries_balanced(entries)


class TestValidation:
    def test_balanced_rou_entries_pass(self):
        entries = [
            {"account_code": "1520", "debit_amount": 1000.0, "credit_amount": 0},
            {"account_code": "2501", "debit_amount": 0, "credit_amount": 1000.0},
        ]
        result = validate_ifrs_transaction(entries)
        assert result.valid is True


class TestStandardMismatch:
    @pytest.mark.asyncio
    async def test_cas_account_set_raises_standard_mismatch(self):
        from ifrs import service as ifrs_svc

        account_set = MagicMock()
        account_set.standard = STANDARD_CAS

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = account_set
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(StandardMismatchError):
            await ifrs_svc.record_fair_value_adjustment(
                db,
                account_set_id="as-cas",
                account_code="1510",
                period_code="202501",
                carrying_amount=1000.0,
                fair_value=1200.0,
                voucher_date=__import__("datetime").date(2025, 1, 15),
                user_id="user-1",
            )

    @pytest.mark.asyncio
    async def test_ifrs_account_set_allows_validation(self):
        from ifrs import service as ifrs_svc

        account_set = MagicMock()
        account_set.standard = STANDARD_IFRS

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = account_set
        db.execute = AsyncMock(return_value=result_mock)

        result = await ifrs_svc.validate_ifrs_transaction_for_account_set(
            db,
            account_set_id="as-ifrs",
            entries=[
                {"account_code": "1520", "debit_amount": 100.0, "credit_amount": 0},
                {"account_code": "2501", "debit_amount": 0, "credit_amount": 100.0},
            ],
        )
        assert result.valid is True


class TestRecognizeRevenue:
    @pytest.mark.asyncio
    async def test_exceeds_allocated_value_rejected(self):
        from ifrs import service as ifrs_svc

        account_set = MagicMock()
        account_set.standard = STANDARD_IFRS
        obligation = MagicMock()
        obligation.id = "ob-1"
        obligation.description = "Software license"
        obligation.allocated_value = 1000.0
        obligation.recognized_to_date = 900.0
        obligation.is_satisfied = False

        db = AsyncMock()
        account_set_result = MagicMock()
        account_set_result.scalar_one_or_none.return_value = account_set
        obligation_result = MagicMock()
        obligation_result.scalar_one_or_none.return_value = obligation
        db.execute = AsyncMock(side_effect=[account_set_result, obligation_result])

        with patch.object(ifrs_svc, "assert_period_open", AsyncMock()):
            with pytest.raises(HTTPException) as exc_info:
                await ifrs_svc.recognize_revenue(
                    db,
                    account_set_id="as-ifrs",
                    obligation_id="ob-1",
                    amount=200.0,
                    period_code="202501",
                    voucher_date=__import__("datetime").date(2025, 1, 31),
                    user_id="user-1",
                )
        assert exc_info.value.status_code == 422
        detail = exc_info.value.detail
        assert detail["standard_reference"] == "IFRS 15"
