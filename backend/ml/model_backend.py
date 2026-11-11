"""
Forecast model training and inference backends.

Uses Prophet when installed; otherwise a lightweight seasonal stub suitable for tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from ml.metrics import mae, mape, rmse

MODEL_TYPE_PROPHET = "Prophet"
MODEL_TYPE_NBEATS = "NBEATS"
MODEL_TYPE_STUB = "StubSeasonal"


@dataclass
class TrainedModelBundle:
    model_type: str
    artifact: Any
    mape: float
    rmse: float
    mae: float
    data_points: int
    training_start: str
    training_end: str
    hyperparameters: dict[str, Any]


def select_model_candidates(months: int) -> list[str]:
    if months < 6:
        return []
    if months < 24:
        return [MODEL_TYPE_PROPHET]
    return [MODEL_TYPE_PROPHET, MODEL_TYPE_NBEATS]


def _use_prophet() -> bool:
    if os.getenv("ML_BACKEND", "").lower() in ("stub", "test"):
        return False
    try:
        import prophet  # noqa: F401

        return True
    except ImportError:
        return False


class _StubSeasonalModel:
    """Simple seasonal naive model with uncertainty bands."""

    def __init__(self, history: pd.DataFrame) -> None:
        self.history = history.copy()
        self._mean = float(history["net_cash_flow"].mean())
        self._std = float(history["net_cash_flow"].std() or abs(self._mean) * 0.1 or 1.0)
        self._inflow_ratio = (
            float(history["inflow"].sum() / max(history["inflow"].sum() + history["outflow"].sum(), 1))
        )

    def predict(self, horizon: int) -> list[dict[str, float]]:
        predictions: list[dict[str, float]] = []
        values = self.history["net_cash_flow"].tolist()
        for step in range(horizon):
            seasonal = values[(len(values) - 12 + step) % len(values)] if values else self._mean
            net = 0.7 * seasonal + 0.3 * self._mean
            spread = max(self._std * 1.96, abs(net) * 0.15, 1.0)
            inflow = max(net * self._inflow_ratio, 0.0)
            outflow = max(inflow - net, 0.0)
            predictions.append(
                {
                    "predicted_inflow": inflow,
                    "predicted_outflow": outflow,
                    "predicted_net_cash_flow": net,
                    "confidence_lower": net - spread,
                    "confidence_upper": net + spread,
                }
            )
        return predictions


def _train_stub(df: pd.DataFrame) -> _StubSeasonalModel:
    return _StubSeasonalModel(df)


def _train_prophet(df: pd.DataFrame) -> Any:
    if not _use_prophet():
        return _train_stub(df)

    from prophet import Prophet

    prophet_df = pd.DataFrame(
        {
            "ds": pd.to_datetime(df["period_code"].astype(str), format="%Y%m"),
            "y": df["net_cash_flow"].astype(float),
        }
    )
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        interval_width=0.8,
    )
    model.fit(prophet_df)
    return model


def _predict_prophet(model: Any, horizon: int, history: pd.DataFrame) -> list[dict[str, float]]:
    if isinstance(model, _StubSeasonalModel):
        return model.predict(horizon)

    future = model.make_future_dataframe(periods=horizon, freq="MS")
    forecast = model.predict(future).tail(horizon)
    inflow_ratio = float(
        history["inflow"].sum() / max(history["inflow"].sum() + history["outflow"].sum(), 1)
    )
    rows: list[dict[str, float]] = []
    for _, row in forecast.iterrows():
        net = float(row["yhat"])
        spread = max(float(row["yhat_upper"] - row["yhat_lower"]) / 2, abs(net) * 0.05, 1.0)
        inflow = max(net * inflow_ratio, 0.0)
        outflow = max(inflow - net, 0.0)
        rows.append(
            {
                "predicted_inflow": inflow,
                "predicted_outflow": outflow,
                "predicted_net_cash_flow": net,
                "confidence_lower": net - spread,
                "confidence_upper": net + spread,
            }
        )
    return rows


def _train_nbeats_challenger(df: pd.DataFrame) -> _StubSeasonalModel:
    """N-BEATS challenger stub — slightly smoothed seasonal model for comparison."""
    smoothed = df.copy()
    smoothed["net_cash_flow"] = smoothed["net_cash_flow"].rolling(window=3, min_periods=1).mean()
    return _StubSeasonalModel(smoothed)


def walk_forward_scores(df: pd.DataFrame, model_type: str) -> tuple[float, float, float]:
    values = df["net_cash_flow"].astype(float).tolist()
    if len(values) < 3:
        return 0.0, 0.0, 0.0

    actuals: list[float] = []
    preds: list[float] = []
    max_splits = min(3, len(values) - 1)
    for split in range(max_splits):
        train_end = len(values) - max_splits + split
        if train_end < 2:
            continue
        train_df = df.iloc[:train_end]
        test_value = values[train_end]
        if model_type == MODEL_TYPE_NBEATS:
            model = _train_nbeats_challenger(train_df)
        elif model_type == MODEL_TYPE_PROPHET and _use_prophet():
            model = _train_prophet(train_df)
        else:
            model = _train_stub(train_df)
        prediction = model.predict(1)[0]["predicted_net_cash_flow"]
        actuals.append(test_value)
        preds.append(prediction)

    if not actuals:
        return 0.0, 0.0, 0.0
    return mape(actuals, preds), rmse(actuals, preds), mae(actuals, preds)


def train_candidate(df: pd.DataFrame, model_type: str) -> TrainedModelBundle:
    if model_type == MODEL_TYPE_NBEATS:
        artifact = _train_nbeats_challenger(df)
        hyper = {"model": "nbeats_stub", "lookback": 3}
    elif model_type == MODEL_TYPE_PROPHET:
        artifact = _train_prophet(df)
        hyper = {"model": "prophet" if _use_prophet() else "stub_seasonal"}
    else:
        artifact = _train_stub(df)
        hyper = {"model": "stub_seasonal"}

    cv_mape, cv_rmse, cv_mae = walk_forward_scores(df, model_type)
    resolved_type = (
        MODEL_TYPE_STUB
        if isinstance(artifact, _StubSeasonalModel) and model_type == MODEL_TYPE_PROPHET
        else model_type
    )
    return TrainedModelBundle(
        model_type=resolved_type,
        artifact=artifact,
        mape=cv_mape,
        rmse=cv_rmse,
        mae=cv_mae,
        data_points=len(df),
        training_start=str(df["period_code"].iloc[0]),
        training_end=str(df["period_code"].iloc[-1]),
        hyperparameters=hyper,
    )


def predict_horizon(model: Any, history: pd.DataFrame, horizon: int) -> list[dict[str, float]]:
    if isinstance(model, _StubSeasonalModel):
        return model.predict(horizon)
    return _predict_prophet(model, horizon, history)
