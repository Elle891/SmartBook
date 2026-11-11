"""
ML Forecast Engine service layer (Task 28).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ml.data_access import (
    count_new_transactions_since,
    load_account_balances_for_period,
    load_training_rows,
)
from ml.errors import ForecastError, ForecastValidationError, InsufficientDataError, ModelNotReadyError
from ml.export import export_forecast_csv, export_forecast_pdf
from ml.feature_engineering import build_monthly_cashflow_frame, compute_ledger_net_cash_flow, count_data_months
from ml.inference import get_forecast, validate_horizon
from ml.training import train_model
from models.ml import ForecastModel, ForecastSnapshot


def _http_error(exc: ForecastError) -> HTTPException:
    code = status.HTTP_422_UNPROCESSABLE_ENTITY
    if isinstance(exc, ModelNotReadyError):
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HTTPException(status_code=code, detail=exc.to_dict())


async def get_model_metrics(
    db: AsyncSession,
    *,
    account_set_id: str,
) -> dict[str, Any]:
    result = await db.execute(
        select(ForecastModel).where(
            ForecastModel.account_set_id == account_set_id,
            ForecastModel.is_active.is_(True),
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise _http_error(ModelNotReadyError())

    bank_rows, ledger_rows = await load_training_rows(db, account_set_id=account_set_id)
    frame = build_monthly_cashflow_frame(bank_rows, ledger_rows)

    return {
        "model_id": str(model.id),
        "model_type": model.model_type,
        "mape": float(model.mape),
        "rmse": float(model.rmse),
        "trained_at": model.trained_at.isoformat(),
        "data_points": count_data_months(frame),
        "artifact_path": model.artifact_path,
    }


async def compare_forecast_vs_actual(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
) -> dict[str, Any]:
    snapshots = await db.execute(
        select(ForecastSnapshot).where(
            ForecastSnapshot.account_set_id == account_set_id,
            ForecastSnapshot.target_period == period_code,
        )
    )
    rows = list(snapshots.scalars())
    balances = await load_account_balances_for_period(
        db, account_set_id=account_set_id, period_code=period_code
    )
    actual = compute_ledger_net_cash_flow(balances)

    comparisons = []
    for snap in rows:
        if snap.actual_net_cash_flow is None and balances:
            snap.actual_net_cash_flow = actual
        comparisons.append(
            {
                "snapshot_period": snap.snapshot_period,
                "target_period": snap.target_period,
                "predicted_net_cash_flow": float(snap.predicted_net_cash_flow or 0),
                "confidence_lower": float(snap.confidence_lower or 0),
                "confidence_upper": float(snap.confidence_upper or 0),
                "actual_net_cash_flow": float(snap.actual_net_cash_flow or actual),
            }
        )

    if balances:
        await db.execute(
            update(ForecastSnapshot)
            .where(
                ForecastSnapshot.account_set_id == account_set_id,
                ForecastSnapshot.target_period == period_code,
                ForecastSnapshot.actual_net_cash_flow.is_(None),
            )
            .values(actual_net_cash_flow=actual)
        )

    return {
        "period_code": period_code,
        "actual_net_cash_flow": actual,
        "comparisons": comparisons,
    }


async def export_forecast(
    db: AsyncSession,
    *,
    account_set_id: str,
    horizon_months: int,
    export_format: str,
) -> tuple[bytes, str, str]:
    try:
        validate_horizon(horizon_months)
        forecast = await get_forecast(
            db, account_set_id=account_set_id, horizon_months=horizon_months
        )
        metrics = await get_model_metrics(db, account_set_id=account_set_id)
    except ForecastError as exc:
        raise _http_error(exc) from exc

    payload = {**forecast, "metrics": metrics}
    fmt = export_format.lower()
    if fmt == "csv":
        return export_forecast_csv(payload), "text/csv", "forecast.csv"
    if fmt == "pdf":
        return export_forecast_pdf(payload), "application/pdf", "forecast.pdf"
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="export_format must be pdf or csv.",
    )


async def schedule_retraining(
    db: AsyncSession,
    *,
    account_set_id: str,
    min_new_transactions: int = 30,
) -> dict[str, Any]:
    active = await db.execute(
        select(ForecastModel).where(
            ForecastModel.account_set_id == account_set_id,
            ForecastModel.is_active.is_(True),
        )
    )
    model = active.scalar_one_or_none()
    since = model.trained_at if model else None
    new_count = await count_new_transactions_since(
        db, account_set_id=account_set_id, since=since
    )
    if new_count < min_new_transactions:
        return {
            "scheduled": False,
            "new_transactions": new_count,
            "threshold": min_new_transactions,
        }

    from app.tasks import train_forecast_model_task

    task = train_forecast_model_task.delay(account_set_id)
    return {
        "scheduled": True,
        "task_id": task.id,
        "new_transactions": new_count,
        "threshold": min_new_transactions,
    }


async def request_forecast(
    db: AsyncSession,
    *,
    account_set_id: str,
    horizon_months: int,
) -> dict[str, Any]:
    try:
        return await get_forecast(
            db, account_set_id=account_set_id, horizon_months=horizon_months
        )
    except ForecastError as exc:
        raise _http_error(exc) from exc


async def request_training(
    db: AsyncSession,
    *,
    account_set_id: str,
) -> dict[str, Any]:
    try:
        return await train_model(db, account_set_id=account_set_id)
    except InsufficientDataError as exc:
        raise _http_error(exc) from exc
