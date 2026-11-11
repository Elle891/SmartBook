"""
Unit tests for Report Engine — summary, export, filters, templates, data sources.

_Requirements: 9.7–9.15 (Tasks 18.3–18.6)_
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.report_engine import MODE_API, MODE_DATA_SERVER, MODE_LEDGER, TEMPLATE_PUBLISHED
from reports.builders import build_cash_flow_statement
from reports.errors import MethodNotSupportedError, ReportValidationError, StandardMismatchError
from reports.export import export_report_csv
from reports.filters import ReportFilter
from reports.formatters import convert_amount, format_amount
from reports.terminology import REPORT_TITLES, STANDARD_CAS, STANDARD_IFRS


SAMPLE_ROWS = [
    {
        "account_code": "1001",
        "account_name": "Cash",
        "account_type": "Asset",
        "opening_balance": 1000.0,
        "total_debits": 500.0,
        "total_credits": 200.0,
        "closing_balance": 1300.0,
    },
    {
        "account_code": "2202",
        "account_name": "Payables",
        "account_type": "Liability",
        "opening_balance": 0.0,
        "total_debits": 0.0,
        "total_credits": 800.0,
        "closing_balance": 800.0,
    },
    {
        "account_code": "3001",
        "account_name": "Equity",
        "account_type": "Equity",
        "opening_balance": 1000.0,
        "total_debits": 0.0,
        "total_credits": 0.0,
        "closing_balance": 1000.0,
    },
    {
        "account_code": "6001",
        "account_name": "Revenue",
        "account_type": "Revenue",
        "opening_balance": 0.0,
        "total_debits": 0.0,
        "total_credits": 2000.0,
        "closing_balance": -2000.0,
    },
    {
        "account_code": "6602",
        "account_name": "Expense",
        "account_type": "Expense",
        "opening_balance": 0.0,
        "total_debits": 1500.0,
        "total_credits": 0.0,
        "closing_balance": 1500.0,
    },
]


class TestReportFilters:
    def test_rejects_invalid_date_range(self):
        filt = ReportFilter(
            date_from=date(2025, 2, 1),
            date_to=date(2025, 1, 1),
        )
        with pytest.raises(ReportValidationError):
            filt.validate()

    def test_rejects_both_entity_filters(self):
        filt = ReportFilter(
            period_code="202501",
            entity_id="e1",
            entity_group_id="g1",
        )
        with pytest.raises(ReportValidationError):
            filt.validate()


class TestCurrencyFormatting:
    def test_cny_format(self):
        assert format_amount(1234.5, "CNY") == "¥1,234.50"

    def test_usd_conversion_from_cny_base(self):
        converted = convert_amount(725.0, from_currency="CNY", to_currency="USD")
        assert converted == 100.0


class TestAccountSummaryBuilder:
    def test_summary_row_count(self):
        from reports.builders import build_account_summary_report

        report = build_account_summary_report(
            standard=STANDARD_CAS, rows=SAMPLE_ROWS, currency="CNY"
        )
        assert report["row_count"] == len(SAMPLE_ROWS)
        assert report["rows"][0]["total_debits"] == 500.0


class TestExport:
    def test_csv_export_contains_title(self):
        from reports.builders import build_income_statement

        report = build_income_statement(
            standard=STANDARD_CAS, rows=SAMPLE_ROWS, currency="CNY"
        )
        csv_bytes = export_report_csv(report)
        assert "利润表".encode("utf-8") in csv_bytes or b"Income" in csv_bytes


class TestCashFlowMethods:
    def test_direct_and_indirect_same_net_change(self):
        direct = build_cash_flow_statement(
            standard=STANDARD_IFRS,
            rows=SAMPLE_ROWS,
            currency="CNY",
            method="Direct",
        )
        indirect = build_cash_flow_statement(
            standard=STANDARD_IFRS,
            rows=SAMPLE_ROWS,
            currency="CNY",
            method="Indirect",
        )
        assert direct["net_change_in_cash"] == indirect["net_change_in_cash"]


class TestDisclosureNotes:
    @pytest.mark.asyncio
    async def test_cas_raises_standard_mismatch(self):
        from reports import service as rpt_svc

        account_set = MagicMock()
        account_set.standard = STANDARD_CAS
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=account_set))
        )
        filt = ReportFilter(period_code="202501")
        with pytest.raises(StandardMismatchError):
            await rpt_svc.generate_disclosure_notes(
                db, account_set_id="as-1", filters=filt
            )


class TestDataSources:
    @pytest.mark.asyncio
    async def test_register_ledger_source(self):
        from reports import data_sources as ds_svc

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        source = await ds_svc.register_data_source(
            db,
            account_set_id="as-1",
            name="Ledger",
            connection_mode=MODE_LEDGER,
        )
        assert source.connection_mode == MODE_LEDGER

    @pytest.mark.asyncio
    async def test_invalid_vendor_rejected(self):
        from reports import data_sources as ds_svc

        db = AsyncMock()
        with pytest.raises(ReportValidationError):
            await ds_svc.register_data_source(
                db,
                account_set_id="as-1",
                name="Bad DB",
                connection_mode=MODE_DATA_SERVER,
                vendor="PostgreSQL",
                host="localhost",
                database_name="db",
            )

    @pytest.mark.asyncio
    async def test_mysql_oracle_sqlserver_stub_test(self):
        from reports import data_sources as ds_svc

        for vendor in ("MySQL", "Oracle", "SQLServer"):
            source = MagicMock()
            source.connection_mode = MODE_DATA_SERVER
            source.vendor = vendor
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = source
            db.execute = AsyncMock(return_value=result)
            db.flush = AsyncMock()
            outcome = await ds_svc.test_data_source_connection(
                db, account_set_id="as-1", data_source_id="ds-1"
            )
            assert outcome["success"] is True


class TestTemplates:
    @pytest.mark.asyncio
    async def test_publish_sets_role_access(self):
        from reports import templates as tpl_svc

        template = MagicMock()
        template.status = "Draft"
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = template
        db.execute = AsyncMock(return_value=result)
        db.flush = AsyncMock()

        published = await tpl_svc.publish_report_template(
            db,
            account_set_id="as-1",
            template_id="t-1",
            role_ids=["role-finance"],
        )
        assert published.status == TEMPLATE_PUBLISHED
        assert published.published_role_ids == ["role-finance"]

    @pytest.mark.asyncio
    async def test_list_filters_by_role(self):
        from reports import templates as tpl_svc

        visible = MagicMock()
        visible.status = TEMPLATE_PUBLISHED
        visible.published_role_ids = ["role-a"]
        hidden = MagicMock()
        hidden.status = TEMPLATE_PUBLISHED
        hidden.published_role_ids = ["role-b"]

        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [visible, hidden]
        db.execute = AsyncMock(return_value=result)

        rows = await tpl_svc.list_report_templates(
            db, account_set_id="as-1", role_id="role-a"
        )
        assert rows == [visible]


class TestTerminology:
    def test_cas_and_ifrs_titles_differ(self):
        assert REPORT_TITLES[STANDARD_CAS]["balance_sheet"] != REPORT_TITLES[STANDARD_IFRS]["balance_sheet"]

    @pytest.mark.asyncio
    async def test_cas_direct_cash_flow_not_supported(self):
        from reports import service as rpt_svc

        account_set = MagicMock()
        account_set.standard = STANDARD_CAS
        account_set.base_currency = "CNY"
        filt = ReportFilter(period_code="202501", cash_flow_method="Direct")

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=account_set)),
                MagicMock(scalar_one=MagicMock(return_value=0)),
            ]
        )
        with pytest.raises(MethodNotSupportedError):
            await rpt_svc.generate_cash_flow_statement(
                db, account_set_id="as-1", filters=filt
            )
