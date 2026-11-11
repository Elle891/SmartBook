"""
Unit tests for ML Forecast Engine (Task 28).
"""

from __future__ import annotations

import os
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

os.environ["ML_BACKEND"] = "stub"
os.environ["ML_STORAGE_BACKEND"] = "memory"

from ml import storage
from ml.errors import ForecastValidationError, InsufficientDataError, ModelNotReadyError
from ml.feature_engineering import add_time_series_features, build_monthly_cashflow_frame
from ml.inference import get_forecast, validate_horizon
from ml.metrics import mape, rmse
from ml.model_backend import select_model_candidates, train_candidate
from ml.periods import next_period_code
from ml.training import train_model


class TestFeatureEngineering:
    def test_build_monthly_frame_with_bank_rows(self):
        rows = [
            SimpleNamespace(date=date(2024, 1, 15), amount=1000.0, direction="Inflow"),
            SimpleNamespace(date=date(2024, 1, 20), amount=400.0, direction="Outflow"),
            SimpleNamespace(date=date(2024, 2, 10), amount=500.0, direction="Inflow"),
        ]
        frame = build_monthly_cashflow_frame(rows, [])
        assert "202401" in frame["period_code"].tolist()
        assert "lag_1" in frame.columns
        assert "mean_3m" in frame.columns

    def test_calendar_features(self):
        df = pd.DataFrame(
            {
                "period_code": ["202412", "202503"],
                "inflow": [1.0, 2.0],
                "outflow": [0.5, 1.0],
                "net_cash_flow": [0.5, 1.0],
            }
        )
        enriched = add_time_series_features(df)
        assert enriched.loc[0, "is_year_end"] == 1
        assert enriched.loc[1, "is_quarter_end"] == 1


class TestModelBackend:
    def test_select_prophet_for_six_to_twenty_three_months(self):
        assert select_model_candidates(6) == ["Prophet"]
        assert select_model_candidates(23) == ["Prophet"]

    def test_select_challenger_for_long_history(self):
        assert "NBEATS" in select_model_candidates(24)

    def test_train_stub_produces_metrics(self):
        history = pd.DataFrame(
            {
                "period_code": [f"2023{m:02d}" for m in range(1, 13)],
                "inflow": [1000.0] * 12,
                "outflow": [700.0] * 12,
                "net_cash_flow": [300.0] * 12,
            }
        )
        bundle = train_candidate(history, "Prophet")
        assert bundle.mape >= 0.0
        assert bundle.data_points == 12


class TestPeriodHelpers:
    def test_next_period_rollover(self):
        assert next_period_code("202412") == "202501"


class TestInferenceValidation:
    def test_horizon_out_of_range(self):
        with pytest.raises(ForecastValidationError):
            validate_horizon(0)
        with pytest.raises(ForecastValidationError):
            validate_horizon(13)


class TestTrainingPipeline:
    @pytest.mark.asyncio
    async def test_train_model_insufficient_data(self):
        db = AsyncMock()
        with patch(
            "ml.training.load_training_rows",
            AsyncMock(return_value=([], [])),
        ):
            with pytest.raises(InsufficientDataError):
                await train_model(db, account_set_id=str(uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_train_model_promotes_and_persists(self):
        storage.clear_memory_store()
        rows = []
        for month in range(1, 13):
            rows.append(
                SimpleNamespace(
                    date=date(2024, month, 1),
                    amount=1000.0 + month * 10,
                    direction="Inflow" if month % 2 else "Outflow",
                )
            )

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch(
            "ml.training.load_training_rows",
            AsyncMock(return_value=(rows, [])),
        ), patch("ml.training.save_forecast_snapshot", AsyncMock()):
            result = await train_model(db, account_set_id=str(uuid.uuid4()))

        assert result["promoted"] is True
        assert "model_id" in result


class TestGetForecast:
    @pytest.mark.asyncio
    async def test_raises_when_no_active_model(self):
        db = AsyncMock()
        rows = [
            SimpleNamespace(date=date(2024, m, 1), amount=100.0, direction="Inflow")
            for m in range(1, 13)
        ]
        model_result = MagicMock()
        model_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=model_result)

        with patch(
            "ml.inference.load_training_rows",
            AsyncMock(return_value=(rows, [])),
        ), patch(
            "ml.inference.resolve_forecast_start_period",
            AsyncMock(return_value="202501"),
        ):
            with pytest.raises(ModelNotReadyError):
                await get_forecast(db, account_set_id=str(uuid.uuid4()), horizon_months=3)


class TestMetrics:
    def test_mape_and_rmse(self):
        actual = [100.0, 200.0, 300.0]
        predicted = [110.0, 190.0, 330.0]
        assert mape(actual, predicted) > 0.0
        assert rmse(actual, predicted) > 0.0
