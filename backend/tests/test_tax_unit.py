"""
Unit tests for Tax Module — aggregation, adjustment, submission failure.

_Requirements: 21.1–21.7 (Task 19.1)_
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tax import aggregation
from tax.aggregation import TAX_TYPE_VAT, apply_line_adjustment, build_vat_report


SAMPLE_ROWS = [
    {
        "account_code": "6001",
        "account_name": "Revenue",
        "account_type": "Revenue",
        "total_debits": 0.0,
        "total_credits": 100000.0,
        "closing_balance": -100000.0,
    },
    {
        "account_code": "22210105",
        "account_name": "Output VAT",
        "account_type": "Liability",
        "total_debits": 0.0,
        "total_credits": 13000.0,
        "closing_balance": 13000.0,
    },
    {
        "account_code": "22210101",
        "account_name": "Input VAT",
        "account_type": "Asset",
        "total_debits": 5000.0,
        "total_credits": 0.0,
        "closing_balance": 5000.0,
    },
]


class TestFilingAggregation:
    def test_vat_report_aggregates_sales_and_tax(self):
        report = build_vat_report(SAMPLE_ROWS, period_code="202501")
        assert report["tax_type"] == TAX_TYPE_VAT
        assert report["summary"]["vat_payable"] == 8000.0
        assert len(report["line_items"]) == 4

    def test_cit_report_computes_taxable_income(self):
        rows = SAMPLE_ROWS + [
            {
                "account_code": "6602",
                "account_name": "Admin expense",
                "account_type": "Expense",
                "total_debits": 40000.0,
                "total_credits": 0.0,
                "closing_balance": 40000.0,
            }
        ]
        report = aggregation.build_cit_report(rows, period_code="202501")
        assert report["summary"]["taxable_income"] == 60000.0
        assert report["summary"]["cit_payable"] == 15000.0


class TestLineAdjustment:
    def test_adjust_output_vat_recalculates_payable(self):
        report = build_vat_report(SAMPLE_ROWS, period_code="202501")
        updated = apply_line_adjustment(report, "output_vat", 15000.0)
        assert updated["summary"]["vat_payable"] == 10000.0

    def test_non_editable_line_rejected(self):
        report = build_vat_report(SAMPLE_ROWS, period_code="202501")
        with pytest.raises(ValueError):
            apply_line_adjustment(report, "vat_payable", 1.0)


class TestSubmitFiling:
    @pytest.mark.asyncio
    async def test_success_records_confirmation(self):
        from tax import service as tax_svc

        filing = MagicMock()
        filing.id = "filing-ok-123"
        filing.tax_type = "VAT"
        filing.period_code = "202501"
        filing.status = "Draft"
        filing.report_data = {"line_items": []}
        filing.confirmation_number = None
        filing.submitted_at = None

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = filing
        db.execute = AsyncMock(return_value=result_mock)
        db.flush = AsyncMock()

        with patch.object(
            tax_svc.clients,
            "submit_to_tax_authority",
            AsyncMock(
                return_value={
                    "success": True,
                    "confirmation_number": "CN-VAT-001",
                    "message": "OK",
                }
            ),
        ):
            result = await tax_svc.submit_filing(
                db, account_set_id="as-1", filing_id="filing-ok-123"
            )

        assert result["success"] is True
        assert filing.status == "Submitted"
        assert filing.confirmation_number == "CN-VAT-001"
        assert filing.submitted_at is not None

    @pytest.mark.asyncio
    async def test_failure_preserves_report_data(self):
        from tax import service as tax_svc

        filing = MagicMock()
        filing.id = "fail-abc"
        filing.tax_type = "VAT"
        filing.period_code = "202501"
        filing.status = "Draft"
        filing.report_data = {"line_items": [{"line_id": "output_vat", "amount": 13000.0}]}
        filing.confirmation_number = None
        filing.submitted_at = None

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = filing
        db.execute = AsyncMock(return_value=result_mock)
        db.flush = AsyncMock()

        with patch.object(
            tax_svc.clients,
            "submit_to_tax_authority",
            AsyncMock(
                return_value={
                    "success": False,
                    "confirmation_number": None,
                    "message": "Invalid period",
                }
            ),
        ):
            result = await tax_svc.submit_filing(
                db, account_set_id="as-1", filing_id="fail-abc"
            )

        assert result["success"] is False
        assert filing.status == "Failed"
        assert filing.report_data["last_submission_error"] == "Invalid period"
        assert filing.report_data["line_items"][0]["amount"] == 13000.0
        assert result["report_data_preserved"] is True


class TestFilingHistory:
    @pytest.mark.asyncio
    async def test_history_returns_submitted_only(self):
        from tax import service as tax_svc

        submitted = MagicMock()
        submitted.id = "f1"
        submitted.period_code = "202501"
        submitted.tax_type = "VAT"
        submitted.status = "Submitted"
        submitted.confirmation_number = "CN-1"
        submitted.submitted_at = datetime(2025, 2, 1, tzinfo=timezone.utc)
        submitted.created_at = datetime(2025, 1, 31, tzinfo=timezone.utc)

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [submitted]
        db.execute = AsyncMock(return_value=result_mock)

        history = await tax_svc.get_filing_history(db, account_set_id="as-1")
        assert len(history) == 1
        assert history[0]["confirmation_number"] == "CN-1"


class TestAdjustDraftOnly:
    @pytest.mark.asyncio
    async def test_adjust_submitted_filing_rejected(self):
        from tax import service as tax_svc

        filing = MagicMock()
        filing.status = "Submitted"
        filing.report_data = {}

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = filing
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc:
            await tax_svc.adjust_line_item(
                db,
                account_set_id="as-1",
                filing_id="f1",
                line_id="output_vat",
                value=100.0,
            )
        assert exc.value.status_code == 409
