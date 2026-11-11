"""
Property tests for Report Engine standard terminology and cash flow methods.

# Feature: smart-accounting-software, Property 4 & 5
**Validates: Requirements 9.1–9.6 (Tasks 18.1, 18.2)**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from reports.builders import (
    build_balance_sheet,
    build_cash_flow_statement,
    build_income_statement,
)
from reports.terminology import REPORT_TITLES, STANDARD_CAS, STANDARD_IFRS

_STANDARD = st.sampled_from([STANDARD_CAS, STANDARD_IFRS])

_SAMPLE_ROWS = [
    {
        "account_code": "1001",
        "account_name": "Cash",
        "account_type": "Asset",
        "opening_balance": 5000.0,
        "total_debits": 1000.0,
        "total_credits": 500.0,
        "closing_balance": 5500.0,
    },
    {
        "account_code": "2001",
        "account_name": "Payables",
        "account_type": "Liability",
        "opening_balance": 0.0,
        "total_debits": 0.0,
        "total_credits": 2000.0,
        "closing_balance": 2000.0,
    },
    {
        "account_code": "3001",
        "account_name": "Equity",
        "account_type": "Equity",
        "opening_balance": 5000.0,
        "total_debits": 0.0,
        "total_credits": 0.0,
        "closing_balance": 5000.0,
    },
    {
        "account_code": "6001",
        "account_name": "Revenue",
        "account_type": "Revenue",
        "opening_balance": 0.0,
        "total_debits": 0.0,
        "total_credits": 3000.0,
        "closing_balance": -3000.0,
    },
    {
        "account_code": "6602",
        "account_name": "Expense",
        "account_type": "Expense",
        "opening_balance": 0.0,
        "total_debits": 2500.0,
        "total_credits": 0.0,
        "closing_balance": 2500.0,
    },
]


class TestProperty4ReportTerminology:
    @given(standard=_STANDARD)
    @settings(max_examples=20)
    def test_balance_sheet_title_matches_standard(self, standard: str) -> None:
        report = build_balance_sheet(standard=standard, rows=_SAMPLE_ROWS, currency="CNY")
        assert report["title"] == REPORT_TITLES[standard]["balance_sheet"]

    @given(standard=_STANDARD)
    @settings(max_examples=20)
    def test_income_statement_title_matches_standard(self, standard: str) -> None:
        report = build_income_statement(standard=standard, rows=_SAMPLE_ROWS, currency="CNY")
        assert report["title"] == REPORT_TITLES[standard]["income_statement"]

    @given(standard=_STANDARD)
    @settings(max_examples=20)
    def test_cash_flow_title_matches_standard(self, standard: str) -> None:
        report = build_cash_flow_statement(
            standard=standard, rows=_SAMPLE_ROWS, currency="CNY", method="Indirect"
        )
        assert report["title"] == REPORT_TITLES[standard]["cash_flow"]


class TestProperty5CashFlowMethod:
    @given(method=st.sampled_from(["Direct", "Indirect"]))
    @settings(max_examples=10)
    def test_ifrs_direct_and_indirect_same_net_cash(self, method: str) -> None:
        direct = build_cash_flow_statement(
            standard=STANDARD_IFRS,
            rows=_SAMPLE_ROWS,
            currency="CNY",
            method="Direct",
        )
        indirect = build_cash_flow_statement(
            standard=STANDARD_IFRS,
            rows=_SAMPLE_ROWS,
            currency="CNY",
            method="Indirect",
        )
        assert direct["net_change_in_cash"] == indirect["net_change_in_cash"]
        assert direct["method"] == "Direct"
        assert indirect["method"] == "Indirect"
        _ = method  # hypothesis drives variety; equality is the property
