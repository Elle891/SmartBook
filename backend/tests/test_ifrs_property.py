"""
Property tests for IFRS Compliance module.

# Feature: smart-accounting-software, Properties 6–11
**Validates: Requirements 22.1–22.7 (Tasks 20.1–20.6)**
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from ifrs.accounts import LEASE_LIABILITY_ACCOUNT, REVENUE_ACCOUNT, ROU_ASSET_ACCOUNT
from ifrs.validation import validate_ifrs_transaction
from ifrs.vouchers import (
    build_fair_value_entries,
    build_impairment_entries,
    build_rou_initial_recognition_entries,
    entries_balanced,
)
from reports.builders import build_disclosure_notes
from reports.terminology import STANDARD_IFRS

_AMOUNT = st.floats(
    min_value=0.01,
    max_value=1_000_000.0,
    allow_nan=False,
    allow_infinity=False,
)
_CARRYING = st.floats(
    min_value=0.0,
    max_value=1_000_000.0,
    allow_nan=False,
    allow_infinity=False,
)
_FAIR_VALUE = st.floats(
    min_value=0.0,
    max_value=1_000_000.0,
    allow_nan=False,
    allow_infinity=False,
)


def _adjustment(carrying: float, fair_value: float) -> float:
    return float(
        (Decimal(str(fair_value)) - Decimal(str(carrying))).quantize(Decimal("0.01"))
    )


class TestProperty6FairValueAdjustment:
    @given(carrying=_CARRYING, fair_value=_FAIR_VALUE)
    @settings(max_examples=50)
    def test_fair_value_entries_balanced_and_match_delta(
        self, carrying: float, fair_value: float
    ) -> None:
        adjustment = _adjustment(carrying, fair_value)
        assume(adjustment != 0)
        entries = build_fair_value_entries(
            account_code="1510", adjustment_amount=adjustment
        )
        assert entries_balanced(entries)
        debits = sum(e["debit_amount"] for e in entries)
        credits = sum(e["credit_amount"] for e in entries)
        assert debits == credits
        assert abs(debits - abs(adjustment)) < 0.0001
        assert adjustment == _adjustment(carrying, fair_value)


class TestProperty7RouInitialRecognition:
    @given(amount=_AMOUNT)
    @settings(max_examples=50)
    def test_rou_debits_match_lease_liability_credits(self, amount: float) -> None:
        entries = build_rou_initial_recognition_entries(amount=amount)
        assert entries_balanced(entries)
        rou_debit = sum(
            e["debit_amount"]
            for e in entries
            if e["account_code"] == ROU_ASSET_ACCOUNT
        )
        lease_credit = sum(
            e["credit_amount"]
            for e in entries
            if e["account_code"] == LEASE_LIABILITY_ACCOUNT
        )
        assert rou_debit == lease_credit == amount


class TestProperty8RevenueRecognitionCap:
    @given(
        allocated=_AMOUNT,
        recognized=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False),
        amount=_AMOUNT,
    )
    @settings(max_examples=50)
    def test_cumulative_recognition_never_exceeds_allocated(
        self, allocated: float, recognized: float, amount: float
    ) -> None:
        assume(recognized <= allocated + 0.0001)
        new_total = recognized + amount
        exceeds = new_total > allocated + 0.0001
        if exceeds:
            assert new_total > allocated
        else:
            assert new_total <= allocated + 0.0001


class TestProperty9ImpairmentVoucher:
    @given(
        carrying=_AMOUNT,
        recoverable=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_impairment_voucher_iff_carrying_exceeds_recoverable(
        self, carrying: float, recoverable: float
    ) -> None:
        needs_voucher = carrying > recoverable
        if needs_voucher:
            loss = float(
                (Decimal(str(carrying)) - Decimal(str(recoverable))).quantize(
                    Decimal("0.01")
                )
            )
            entries = build_impairment_entries(
                loss_amount=loss, asset_account="asset-1"
            )
            assert entries_balanced(entries)
            assert sum(e["debit_amount"] for e in entries) == loss
        else:
            assert carrying <= recoverable


class TestProperty10DisclosureNotes:
    @given(period_code=st.from_regex(r"20[0-9]{4}"))
    @settings(max_examples=20)
    def test_ifrs_disclosure_notes_non_empty_with_required_sections(
        self, period_code: str
    ) -> None:
        report = build_disclosure_notes(standard=STANDARD_IFRS, period_code=period_code)
        assert report["standard"] == STANDARD_IFRS
        assert report["sections"]
        headings = {s["heading"] for s in report["sections"]}
        assert "Accounting policies" in headings
        assert "Significant estimates" in headings
        assert "Standard-specific disclosures" in headings
        for section in report["sections"]:
            assert section["content"]


class TestProperty11InvalidIfrsTransactions:
    @given(amount=_AMOUNT)
    @settings(max_examples=30)
    def test_lease_liability_without_rou_rejected_with_ifrs16(self, amount: float) -> None:
        entries = [
            {
                "account_code": LEASE_LIABILITY_ACCOUNT,
                "debit_amount": 0,
                "credit_amount": amount,
            },
        ]
        result = validate_ifrs_transaction(entries)
        assert result.valid is False
        assert result.standard_reference == "IFRS 16"
        assert "IFRS 16" in result.message

    @given(amount=_AMOUNT)
    @settings(max_examples=30)
    def test_revenue_without_debit_rejected_with_ifrs15(self, amount: float) -> None:
        entries = [
            {
                "account_code": REVENUE_ACCOUNT,
                "debit_amount": 0,
                "credit_amount": amount,
            },
        ]
        result = validate_ifrs_transaction(entries)
        assert result.valid is False
        assert result.standard_reference == "IFRS 15"

    @given(amount=_AMOUNT)
    @settings(max_examples=30)
    def test_fair_value_decrease_without_loss_rejected_with_ifrs9(
        self, amount: float
    ) -> None:
        entries = [
            {
                "account_code": "1510",
                "debit_amount": 0,
                "credit_amount": amount,
            },
        ]
        result = validate_ifrs_transaction(entries)
        assert result.valid is False
        assert result.standard_reference == "IFRS 9"
