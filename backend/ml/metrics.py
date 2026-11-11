"""Forecast evaluation metrics and model promotion rules."""

from __future__ import annotations

import math
from typing import Iterable


def mape(actual: Iterable[float], predicted: Iterable[float]) -> float:
    pairs = [(a, p) for a, p in zip(actual, predicted, strict=True) if a != 0]
    if not pairs:
        return 0.0
    return sum(abs((a - p) / a) for a, p in pairs) / len(pairs) * 100.0


def rmse(actual: Iterable[float], predicted: Iterable[float]) -> float:
    pairs = list(zip(actual, predicted, strict=True))
    if not pairs:
        return 0.0
    return math.sqrt(sum((a - p) ** 2 for a, p in pairs) / len(pairs))


def mae(actual: Iterable[float], predicted: Iterable[float]) -> float:
    pairs = list(zip(actual, predicted, strict=True))
    if not pairs:
        return 0.0
    return sum(abs(a - p) for a, p in pairs) / len(pairs)


def should_promote_model(new_mape: float, current_mape: float | None) -> bool:
    """Property 14: promote only when new MAPE <= current MAPE."""
    if current_mape is None:
        return True
    return new_mape <= current_mape


def validate_confidence_interval(
    *,
    predicted_net: float,
    confidence_lower: float,
    confidence_upper: float,
) -> bool:
    """Property 13: lower <= predicted <= upper."""
    return confidence_lower <= predicted_net <= confidence_upper
