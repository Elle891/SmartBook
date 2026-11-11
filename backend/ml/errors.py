"""ML Forecast Engine errors (Req 23.8, design §1875)."""

from __future__ import annotations


class ForecastError(Exception):
    code: str = "forecast_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class InsufficientDataError(ForecastError):
    code = "insufficient_data"

    def __init__(self, months_available: int, *, minimum: int = 6) -> None:
        super().__init__(
            f"Insufficient historical data: {months_available} month(s) available; "
            f"minimum {minimum} months required.",
            details={"months_available": months_available, "minimum_months": minimum},
        )


class ModelNotReadyError(ForecastError):
    code = "model_not_ready"

    def __init__(self, *, reason: str = "No active forecast model.") -> None:
        super().__init__(reason, details={"reason": reason})


class ForecastValidationError(ForecastError):
    code = "validation_error"
