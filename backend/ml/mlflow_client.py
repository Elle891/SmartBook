"""MLflow experiment logging helpers."""

from __future__ import annotations

import os
from typing import Any


def log_training_run(
    *,
    account_set_id: str,
    model_type: str,
    metrics: dict[str, float],
    hyperparameters: dict[str, Any],
    artifact_path: str,
) -> str | None:
    if os.getenv("MLFLOW_DISABLED", "true").lower() in ("1", "true", "yes"):
        return None
    try:
        import mlflow

        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "file:./mlruns"))
        experiment = f"forecast-{account_set_id}"
        mlflow.set_experiment(experiment)
        with mlflow.start_run(run_name=f"train-{model_type}") as run:
            mlflow.log_params(hyperparameters)
            mlflow.log_metrics(metrics)
            mlflow.log_param("model_type", model_type)
            mlflow.log_param("artifact_path", artifact_path)
            return run.info.run_id
    except Exception:
        return None
