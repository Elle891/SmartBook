"""
Model training pipeline (Task 28) — Celery entry via train_model().
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ml import model_backend, storage
from ml.errors import InsufficientDataError
from ml.feature_engineering import build_monthly_cashflow_frame, count_data_months
from ml.metrics import should_promote_model
from ml.mlflow_client import log_training_run
from ml.data_access import load_training_rows, save_forecast_snapshot
from models.ml import ForecastModel


async def train_model(
    db: AsyncSession,
    *,
    account_set_id: str,
) -> dict[str, Any]:
    bank_rows, ledger_rows = await load_training_rows(db, account_set_id=account_set_id)
    frame = build_monthly_cashflow_frame(bank_rows, ledger_rows)
    months = count_data_months(frame)
    if months < 6:
        raise InsufficientDataError(months)

    candidates = model_backend.select_model_candidates(months)
    best = None
    for candidate in candidates:
        bundle = model_backend.train_candidate(frame, candidate)
        if best is None or bundle.mape < best.mape:
            best = bundle

    assert best is not None

    current = await db.execute(
        select(ForecastModel).where(
            ForecastModel.account_set_id == account_set_id,
            ForecastModel.is_active.is_(True),
        )
    )
    active = current.scalar_one_or_none()
    current_mape = float(active.mape) if active else None

    if not should_promote_model(best.mape, current_mape):
        return {
            "promoted": False,
            "model_type": best.model_type,
            "mape": best.mape,
            "current_mape": current_mape,
            "message": "New model did not improve MAPE; previous model remains active.",
        }

    if active is not None:
        await db.execute(
            update(ForecastModel)
            .where(ForecastModel.id == active.id)
            .values(is_active=False)
        )

    artifact_path = storage.save_model_artifact(account_set_id, best.artifact)
    metadata = {
        "model_type": best.model_type,
        "mape": best.mape,
        "rmse": best.rmse,
        "mae": best.mae,
        "data_points": best.data_points,
        "training_start": best.training_start,
        "training_end": best.training_end,
        "hyperparameters": best.hyperparameters,
        "artifact_path": artifact_path,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    storage.save_metadata(account_set_id, metadata)
    mlflow_run_id = log_training_run(
        account_set_id=account_set_id,
        model_type=best.model_type,
        metrics={"mape": best.mape, "rmse": best.rmse, "mae": best.mae},
        hyperparameters=best.hyperparameters,
        artifact_path=artifact_path,
    )

    model_row = ForecastModel(
        id=uuid.uuid4(),
        account_set_id=uuid.UUID(account_set_id),
        model_type=best.model_type,
        artifact_path=artifact_path,
        trained_at=datetime.now(timezone.utc),
        mape=best.mape,
        rmse=best.rmse,
        is_active=True,
    )
    db.add(model_row)
    await db.flush()

    await save_forecast_snapshot(
        db,
        account_set_id=account_set_id,
        model_id=str(model_row.id),
        history_frame=frame,
        horizon_months=3,
    )

    return {
        "promoted": True,
        "model_id": str(model_row.id),
        "model_type": best.model_type,
        "mape": best.mape,
        "rmse": best.rmse,
        "mae": best.mae,
        "artifact_path": artifact_path,
        "mlflow_run_id": mlflow_run_id,
    }
