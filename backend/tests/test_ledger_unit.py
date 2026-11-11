"""
Unit tests for Ledger Engine — running balance, subsidiary grouping, export formats.

_Requirements: 14.1–14.7 (Task 10.1)_
"""

from __future__ import annotations

import io
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ledger.calculations import (
    compute_closing_balance,
    compute_running_balance,
    group_subsidiary_entries,
    is_bank_account_code,
    is_cash_account_code,
    net_change,
)
from ledger.export import export_to_excel
from ledger.materializer import materialize_voucher


class TestRunningBalance:
    def test_asset_account_debit_increases_balance(self):
        prev = Decimal("1000")
        result = compute_running_balance(prev, "Asset", Decimal("500"), Decimal("0"))
        assert result == Decimal("1500")

    def test_liability_account_credit_increases_balance(self):
        prev = Decimal("2000")
        result = compute_running_balance(prev, "Liability", Decimal("0"), Decimal("300"))
        assert result == Decimal("2300")

    def test_net_change_expense_debit_normal(self):
        assert net_change("Expense", Decimal("100"), Decimal("20")) == Decimal("80")

    def test_closing_balance_from_totals(self):
        closing = compute_closing_balance(
            Decimal("1000"),
            Decimal("500"),
            Decimal("200"),
            "Asset",
        )
        assert closing == Decimal("1300")


class TestAccountCodeClassification:
    def test_cash_codes(self):
        assert is_cash_account_code("1001")
        assert is_cash_account_code("101001")
        assert not is_cash_account_code("1002")

    def test_bank_codes(self):
        assert is_bank_account_code("1002")
        assert is_bank_account_code("102001")
        assert not is_bank_account_code("1001")


class TestSubsidiaryGrouping:
    def test_groups_by_dimension_value(self):
        entries = [
            {
                "entry_date": "2025-01-01",
                "voucher_number": 1,
                "aux_dimension_values": {"department": "Sales"},
            },
            {
                "entry_date": "2025-01-02",
                "voucher_number": 2,
                "aux_dimension_values": {"department": "HR"},
            },
            {
                "entry_date": "2025-01-03",
                "voucher_number": 3,
                "aux_dimension_values": {"department": "Sales"},
            },
        ]
        groups = group_subsidiary_entries(entries, "department")
        assert len(groups) == 2
        sales = next(g for g in groups if g["dimension_value"] == "Sales")
        assert len(sales["entries"]) == 2
        hr = next(g for g in groups if g["dimension_value"] == "HR")
        assert len(hr["entries"]) == 1

    def test_missing_dimension_value_grouped_as_none(self):
        entries = [
            {"entry_date": "2025-01-01", "voucher_number": 1, "aux_dimension_values": {}},
        ]
        groups = group_subsidiary_entries(entries, "department")
        assert groups[0]["dimension_value"] == "(none)"


class TestExportExcel:
    def test_excel_export_has_header_and_data_rows(self):
        rows = [
            {
                "account_code": "1001",
                "account_name": "Cash",
                "opening_balance": 1000.0,
                "total_debits": 500.0,
                "total_credits": 200.0,
                "closing_balance": 1300.0,
            },
        ]
        columns = [
            ("account_code", "Account Code"),
            ("account_name", "Account Name"),
            ("opening_balance", "Opening"),
            ("total_debits", "Debits"),
            ("total_credits", "Credits"),
            ("closing_balance", "Closing"),
        ]
        data = export_to_excel("Summary", rows, columns)
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(data))
        ws = wb.active
        assert ws.cell(1, 1).value == "Account Code"
        assert ws.cell(2, 1).value == "1001"
        assert ws.cell(2, 6).value == 1300.0


class TestMaterializeVoucher:
    @pytest.mark.asyncio
    async def test_skips_already_materialized(self):
        from ledger import materializer as mat

        db = AsyncMock()
        with patch.object(mat, "is_voucher_materialized", AsyncMock(return_value=True)):
            count = await materialize_voucher(db, str(__import__("uuid").uuid4()))
        assert count == 0
        db.add.assert_not_called()
