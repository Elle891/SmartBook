"""
Unit tests for Cashier module — transfer validation, FX balance, reconciliation.

_Requirements: 16.1–16.8 (Task 12.1)_
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException

from cashier.calculations import (
    build_reconciliation_report,
    compute_fx_balance,
    compute_functional_amount,
    validate_transfer_balanced,
)
from cashier.service import _validate_cashier_code


class TestTransferValidation:
    def test_equal_amounts_pass(self):
        validate_transfer_balanced(Decimal("1000"), Decimal("1000"))

    def test_unequal_amounts_raise(self):
        with pytest.raises(ValueError) as exc:
            validate_transfer_balanced(Decimal("1000"), Decimal("999.99"))
        assert "difference" in str(exc.value).lower() or "equal" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_record_transfer_rejects_imbalance(self):
        from unittest.mock import AsyncMock, patch

        from cashier import service as cash_svc

        db = AsyncMock()
        with (
            patch.object(cash_svc, "assert_period_open", AsyncMock()),
            patch.object(cash_svc, "_get_cashier_account", AsyncMock()),
        ):
            with pytest.raises(HTTPException) as exc:
                await cash_svc.record_transfer(
                    db,
                    account_set_id="as-1",
                    from_account_code="1001",
                    to_account_code="1002",
                    income_amount=100.0,
                    expenditure_amount=90.0,
                    period_code="202501",
                    description="xfer",
                    user_id="u1",
                )
        assert exc.value.status_code == 422


class TestFxBalance:
    def test_functional_from_foreign_and_rate(self):
        result = compute_functional_amount(
            Decimal("0"),
            foreign_amount=Decimal("100"),
            exchange_rate=Decimal("7.25"),
        )
        assert result == Decimal("725.0000")

    def test_aggregate_fx_balance(self):
        txns = [
            {
                "primary_account_code": "101001",
                "foreign_currency": "USD",
                "foreign_amount": 100.0,
                "functional_amount": 725.0,
            },
            {
                "primary_account_code": "101001",
                "foreign_currency": "USD",
                "foreign_amount": 50.0,
                "functional_amount": 362.5,
            },
        ]
        report = compute_fx_balance(txns, account_code="101001", base_currency="CNY")
        assert report["foreign_balance"] == 150.0
        assert report["functional_balance"] == 1087.5
        assert report["foreign_currency"] == "USD"
        assert report["effective_exchange_rate"] == pytest.approx(7.25, rel=1e-3)


class TestReconciliation:
    def test_balanced_reconciliation(self):
        report = build_reconciliation_report(
            account_code="1001",
            system_balance=Decimal("5000"),
            physical_count=Decimal("5000"),
        )
        assert report["is_balanced"] is True
        assert report["discrepancy"] == 0.0

    def test_surplus_reported(self):
        report = build_reconciliation_report(
            account_code="1001",
            system_balance=Decimal("5000"),
            physical_count=Decimal("5100"),
        )
        assert report["is_balanced"] is False
        assert report["discrepancy"] == 100.0
        assert "Discrepancy" in report["message"]

    def test_shortage_reported(self):
        report = build_reconciliation_report(
            account_code="1001",
            system_balance=Decimal("5000"),
            physical_count=Decimal("4900"),
        )
        assert report["discrepancy"] == -100.0


class TestCashierAccountRegistration:
    def test_cash_code_validation(self):
        _validate_cashier_code("1001", "Cash")
        _validate_cashier_code("101001", "Cash")

    def test_bank_code_validation(self):
        _validate_cashier_code("1002", "Bank")

    def test_wrong_type_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _validate_cashier_code("1002", "Cash")
        assert exc.value.status_code == 422
