"""
Unit tests for Payment Hub core service (Task 25).
"""

from __future__ import annotations

from datetime import date

from payment import service as payment_svc
from payment.routing_matrix import DOMESTIC_ROUTING_SETTLEMENT


class TestSettlementCutoff:
    def test_returns_cutoff_metadata(self):
        info = payment_svc.get_settlement_cutoff_info(
            routing_method="CNAPS",
            settlement_method="Real_Time_Settlement",
            as_of=date(2025, 6, 1),
        )
        assert "cutoff_time" in info
        assert "next_available_date" in info


class TestExchangeRate:
    def test_same_currency_rate_is_one(self):
        result = payment_svc.get_indicative_exchange_rate(
            source_currency="CNY", target_currency="CNY"
        )
        assert result["rate"] == 1.0


class TestDefaultSettlement:
    def test_set_and_get_default(self):
        payment_svc.set_default_settlement_method(
            account_set_id="as-1",
            routing_method="CNAPS",
            settlement_method="Real_Time_Settlement",
        )
        assert (
            payment_svc.get_default_settlement_method(
                account_set_id="as-1", routing_method="CNAPS"
            )
            == "Real_Time_Settlement"
        )


class TestRoutingMatrix:
    def test_domestic_matrix_has_cnaps(self):
        assert "Real_Time_Settlement" in DOMESTIC_ROUTING_SETTLEMENT["CNAPS"]
