"""
Property tests for domestic routing/settlement options (Task 26.1–26.2).

# Feature: smart-accounting-software, Properties 21–22
**Validates: Requirements 25.2, 25.3, 26.2, 26.3, 26.4**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from bank.routing import ALL_ROUTING_METHODS, get_bank_supported_methods
from payment.routing_matrix import (
    DOMESTIC_ROUTING_SETTLEMENT,
    INTERNATIONAL_ROUTING_SETTLEMENT,
    SCOPE_DOMESTIC,
    SCOPE_INTERNATIONAL,
    build_routing_settlement_options,
    filter_available_routing_methods,
    settlement_methods_for_routing,
)

_ROUTING = st.sampled_from(ALL_ROUTING_METHODS)
_BANK = st.sampled_from(["ICBC", "BOC", "CCB", "ABC", "DEFAULT"])
_CURRENCY = st.sampled_from(["CNY", "USD", "EUR"])
_SCOPE = st.sampled_from([SCOPE_DOMESTIC, SCOPE_INTERNATIONAL])


class TestProperty21SettlementMethodsValidForRouting:
    @given(scope=_SCOPE)
    @settings(max_examples=30)
    def test_matrix_settlement_methods_belong_to_routing(self, scope: str) -> None:
        matrix = (
            INTERNATIONAL_ROUTING_SETTLEMENT
            if scope == SCOPE_INTERNATIONAL
            else DOMESTIC_ROUTING_SETTLEMENT
        )
        for routing, settlements in matrix.items():
            allowed = set(settlement_methods_for_routing(routing, payment_scope=scope))
            assert settlements
            assert set(settlements) <= allowed

    @given(
        scope=_SCOPE,
        configured=st.lists(_ROUTING, min_size=0, max_size=7, unique=True),
        bank=_BANK,
        currency=_CURRENCY,
        same_bank=st.booleans(),
    )
    @settings(max_examples=80)
    def test_presented_settlements_are_subset_of_matrix(
        self,
        scope: str,
        configured: list[str],
        bank: str,
        currency: str,
        same_bank: bool,
    ) -> None:
        routing_methods = filter_available_routing_methods(
            configured_available=set(configured),
            bank_code=bank,
            payment_scope=scope,
            currency=currency,
            same_bank=same_bank,
        )
        options = build_routing_settlement_options(
            routing_methods=routing_methods,
            payment_scope=scope,
        )
        for option in options:
            routing = option["routing_method"]
            allowed = set(settlement_methods_for_routing(routing, payment_scope=scope))
            presented = {item["settlement_method"] for item in option["settlement_methods"]}
            assert presented
            assert presented <= allowed


class TestProperty22RoutingMethodsAreConfiguredAndAvailable:
    @given(
        configured=st.lists(_ROUTING, min_size=0, max_size=7, unique=True),
        bank=_BANK,
        scope=_SCOPE,
        currency=_CURRENCY,
        same_bank=st.booleans(),
    )
    @settings(max_examples=80)
    def test_routing_is_intersection_of_configured_bank_and_scope_rules(
        self,
        configured: list[str],
        bank: str,
        scope: str,
        currency: str,
        same_bank: bool,
    ) -> None:
        configured_set = set(configured)
        bank_supported = set(get_bank_supported_methods(bank))
        expected = filter_available_routing_methods(
            configured_available=configured_set,
            bank_code=bank,
            payment_scope=scope,
            currency=currency,
            same_bank=same_bank,
        )
        options = build_routing_settlement_options(
            routing_methods=expected,
            payment_scope=scope,
        )
        presented = {option["routing_method"] for option in options}
        assert presented == expected
        assert presented <= configured_set
        assert presented <= bank_supported

    @given(
        unconfigured=st.sampled_from(ALL_ROUTING_METHODS),
        bank=_BANK,
    )
    @settings(max_examples=30)
    def test_unconfigured_routing_never_appears(self, unconfigured: str, bank: str) -> None:
        available = filter_available_routing_methods(
            configured_available=set(),
            bank_code=bank,
            payment_scope=SCOPE_DOMESTIC,
            currency="CNY",
            same_bank=True,
        )
        assert unconfigured not in available
