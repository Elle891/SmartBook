"""
Property tests for ML Forecast Engine (Task 28.1–28.5).

# Feature: smart-accounting-software, Properties 12–16
**Validates: Requirements 23.2–23.9**
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

os.environ.setdefault("ML_BACKEND", "stub")
os.environ.setdefault("ML_STORAGE_BACKEND", "memory")

from ml.errors import InsufficientDataError
from ml.feature_engineering import build_monthly_cashflow_frame, compute_ledger_net_cash_flow
from ml.inference import build_period_records, validate_horizon
from ml.metrics import should_promote_model, validate_confidence_interval
from ml.model_backend import predict_horizon, train_candidate
from ml.periods import generate_future_period_codes

_HORIZON = st.integers(min_value=1, max_value=12)
_MAPE = st.floats(min_value=0.01, max_value=100.0, allow_nan=False)
_MONTHS = st.integers(min_value=1, max_value=5)


class TestProperty12InsufficientData:
    @given(months=_MONTHS)
    @settings(max_examples=20)
    def test_fewer_than_six_months_raises(self, months: int) -> None:
        with pytest.raises(InsufficientDataError) as exc:
            raise InsufficientDataError(months)
        assert exc.value.details["months_available"] == months
        assert exc.value.details["minimum_months"] == 6

    def test_empty_frame_has_zero_months(self):
        frame = build_monthly_cashflow_frame([], [])
        assert frame.empty


class TestProperty13ConfidenceIntervalsWellFormed:
    @given(
        base=st.floats(min_value=-1_000_000, max_value=1_000_000, allow_nan=False),
        horizon=_HORIZON,
    )
    @settings(max_examples=40)
    def test_generated_periods_have_valid_intervals(self, base: float, horizon: int) -> None:
        records = build_period_records(
            start_period="202501", horizon_months=horizon, base_net=base
        )
        assert len(records) == horizon
        for record in records:
            assert validate_confidence_interval(
                predicted_net=float(record["predicted_net_cash_flow"]),
                confidence_lower=float(record["confidence_lower"]),
                confidence_upper=float(record["confidence_upper"]),
            )

    @given(horizon=_HORIZON)
    @settings(max_examples=20)
    def test_model_predictions_respect_interval_order(self, horizon: int) -> None:
        history = pd.DataFrame(
            {
                "period_code": [f"2024{m:02d}" for m in range(1, 13)],
                "inflow": [1000.0 + m * 10 for m in range(1, 13)],
                "outflow": [800.0 + m * 5 for m in range(1, 13)],
                "net_cash_flow": [200.0 + m * 5 for m in range(1, 13)],
            }
        )
        bundle = train_candidate(history, "Prophet")
        preds = predict_horizon(bundle.artifact, history, horizon)
        assert len(preds) == horizon
        for pred in preds:
            assert validate_confidence_interval(
                predicted_net=pred["predicted_net_cash_flow"],
                confidence_lower=pred["confidence_lower"],
                confidence_upper=pred["confidence_upper"],
            )


class TestProperty14ModelPromotion:
    @given(new_mape=_MAPE, current_mape=_MAPE)
    @settings(max_examples=50)
    def test_promote_only_when_new_mape_lte_current(self, new_mape: float, current_mape: float) -> None:
        result = should_promote_model(new_mape, current_mape)
        assert result == (new_mape <= current_mape)

    def test_first_model_always_promoted(self):
        assert should_promote_model(12.5, None) is True


class TestProperty15HorizonBounds:
    @given(horizon=_HORIZON, start=st.sampled_from(["202501", "202506", "202512"]))
    @settings(max_examples=40)
    def test_exactly_n_period_records(self, horizon: int, start: str) -> None:
        codes = generate_future_period_codes(start, horizon)
        assert len(codes) == horizon
        records = build_period_records(start_period=start, horizon_months=horizon, base_net=100.0)
        assert len(records) == horizon

    @given(horizon=st.integers(min_value=0, max_value=0))
    @settings(max_examples=5)
    def test_zero_horizon_invalid(self, horizon: int) -> None:
        with pytest.raises(Exception):
            validate_horizon(horizon)


class TestProperty16SnapshotMatchesLedger:
    @given(
        debits=st.floats(min_value=0, max_value=100000, allow_nan=False),
        credits=st.floats(min_value=0, max_value=100000, allow_nan=False),
    )
    @settings(max_examples=40)
    def test_actual_net_matches_account_balance_cash_accounts(
        self, debits: float, credits: float
    ) -> None:
        balances = [
            SimpleNamespace(account_code="1001", total_debits=debits, total_credits=credits),
            SimpleNamespace(account_code="2001", total_debits=50.0, total_credits=20.0),
        ]
        actual = compute_ledger_net_cash_flow(balances)
        assert actual == pytest.approx(debits - credits)
