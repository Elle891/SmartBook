"""
Forecast inference (Task 28).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ml import model_backend, storage
from ml.errors import ForecastValidationError, InsufficientDataError, ModelNotReadyError
from ml.feature_engineering import build_monthly_cashflow_frame, count_data_months
from ml.metrics import validate_confidence_interval
from ml.periods import generate_future_period_codes
from ml.data_access import load_training_rows, resolve_forecast_start_period
from models.ml import ForecastModel, ForecastPeriod, ForecastResult


def validate_horizon(horizon_months: int) -> None:
    if horizon_months < 1 or horizon_months > 12:
        raise ForecastValidationError(
            "horizon_months must be between 1 and 12.",
            details={"horizon_months": horizon_months},
        )


async def get_forecast(
    db: AsyncSession,
    *,
    account_set_id: str,
    horizon_months: int,
) -> dict[str, Any]:
    validate_horizon(horizon_months)

    bank_rows, ledger_rows = await load_training_rows(db, account_set_id=account_set_id)
    history = build_monthly_cashflow_frame(bank_rows, ledger_rows)
    months = count_data_months(history)
    if months < 6:
        raise InsufficientDataError(months)

    model_result = await db.execute(
        select(ForecastModel).where(
            ForecastModel.account_set_id == account_set_id,
            ForecastModel.is_active.is_(True),
        )
    )
    model_row = model_result.scalar_one_or_none()
    if model_row is None:
        raise ModelNotReadyError()

    try:
        artifact = storage.load_model_artifact(account_set_id)
    except FileNotFoundError as exc:
        raise ModelNotReadyError(reason="Active model artifact missing from storage.") from exc

    start_period = await resolve_forecast_start_period(db, account_set_id=account_set_id)
    period_codes = generate_future_period_codes(start_period, horizon_months)
    raw_predictions = model_backend.predict_horizon(artifact, history, horizon_months)

    periods: list[dict[str, Any]] = []
    for period_code, pred in zip(period_codes, raw_predictions, strict=True):
        net = float(pred["predicted_net_cash_flow"])
        lower = float(pred["confidence_lower"])
        upper = float(pred["confidence_upper"])
        if not validate_confidence_interval(
            predicted_net=net, confidence_lower=lower, confidence_upper=upper
        ):
            spread = max(abs(net) * 0.1, 1.0)
            lower, upper = net - spread, net + spread
        periods.append(
            {
                "period_code": period_code,
                "predicted_inflow": float(pred["predicted_inflow"]),
                "predicted_outflow": float(pred["predicted_outflow"]),
                "predicted_net_cash_flow": net,
                "confidence_lower": lower,
                "confidence_upper": upper,
            }
        )

    result_row = ForecastResult(
        id=uuid.uuid4(),
        account_set_id=uuid.UUID(account_set_id),
        model_id=model_row.id,
        generated_at=datetime.now(timezone.utc),
        horizon_months=horizon_months,
    )
    db.add(result_row)
    await db.flush()

    for period in periods:
        db.add(
            ForecastPeriod(
                id=uuid.uuid4(),
                result_id=result_row.id,
                period_code=period["period_code"],
                predicted_inflow=period["predicted_inflow"],
                predicted_outflow=period["predicted_outflow"],
                predicted_net_cash_flow=period["predicted_net_cash_flow"],
                confidence_lower=period["confidence_lower"],
                confidence_upper=period["confidence_upper"],
            )
        )
    await db.flush()

    return {
        "result_id": str(result_row.id),
        "model_id": str(model_row.id),
        "model_type": model_row.model_type,
        "generated_at": result_row.generated_at.isoformat(),
        "horizon_months": horizon_months,
        "start_period": start_period,
        "periods": periods,
    }


def build_period_records(
    *,
    start_period: str,
    horizon_months: int,
    base_net: float,
    spread_ratio: float = 0.15,
) -> list[dict[str, float | str]]:
    """Pure helper for property tests (Property 15)."""
    codes = generate_future_period_codes(start_period, horizon_months)
    records: list[dict[str, float | str]] = []
    for idx, code in enumerate(codes):
        net = base_net + idx * 100.0
        spread = max(abs(net) * spread_ratio, 1.0)
        records.append(
            {
                "period_code": code,
                "predicted_net_cash_flow": net,
                "confidence_lower": net - spread,
                "confidence_upper": net + spread,
            }
        )
    return records
