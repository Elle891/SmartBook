"""
Property test: profit/loss carry-forward targets the correct retained earnings account.

# Feature: smart-accounting-software, Property 3
**Validates: Requirements 15.2, 15.3**
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from period_end.accounts import CARRY_RETAINED_EARNINGS, get_carry_forward_account
from period_end.service import build_pnl_to_retained_entries


_STANDARD_ST = st.sampled_from(["CAS", "IFRS"])
_NET_PROFIT_ST = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
_NET_LOSS_ST = st.decimals(
    min_value=Decimal("-999999.99"),
    max_value=Decimal("-0.01"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


class TestProperty3RetainedEarningsTarget:
    @given(standard=_STANDARD_ST, net_profit=_NET_PROFIT_ST)
    @settings(max_examples=50)
    def test_profit_credits_designated_retained_earnings_account(
        self, standard: str, net_profit: Decimal
    ) -> None:
        retained = get_carry_forward_account(standard, CARRY_RETAINED_EARNINGS)
        pnl = get_carry_forward_account(standard, "profit_loss")
        closing = build_pnl_to_retained_entries(net_profit, pnl, retained)

        credit_lines = [
            e
            for e in closing
            if e["account_code"] == retained and e["credit_amount"] > 0
        ]
        assert len(credit_lines) >= 1
        assert sum(e["credit_amount"] for e in credit_lines) == float(net_profit)

    @given(standard=_STANDARD_ST, net_loss=_NET_LOSS_ST)
    @settings(max_examples=50)
    def test_loss_debits_designated_retained_earnings_account(
        self, standard: str, net_loss: Decimal
    ) -> None:
        retained = get_carry_forward_account(standard, CARRY_RETAINED_EARNINGS)
        pnl = get_carry_forward_account(standard, "profit_loss")
        closing = build_pnl_to_retained_entries(net_loss, pnl, retained)

        debit_lines = [
            e
            for e in closing
            if e["account_code"] == retained and e["debit_amount"] > 0
        ]
        assert len(debit_lines) >= 1
        loss = abs(net_loss)
        assert sum(e["debit_amount"] for e in debit_lines) == float(loss)

    @given(standard=_STANDARD_ST)
    @settings(max_examples=10)
    def test_cas_and_ifrs_use_different_retained_accounts(self, standard: str) -> None:
        retained = get_carry_forward_account(standard, CARRY_RETAINED_EARNINGS)
        if standard == "CAS":
            assert retained == "3141"
        else:
            assert retained == "3300"

        other = "IFRS" if standard == "CAS" else "CAS"
        other_retained = get_carry_forward_account(other, CARRY_RETAINED_EARNINGS)
        assert retained != other_retained
