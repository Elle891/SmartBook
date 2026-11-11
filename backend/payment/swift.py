"""SWIFT BIC validation helpers (Task 27)."""

from __future__ import annotations

import re

from bank.errors import RoutingValidationError
from bank.routing import ROUTING_SWIFT, validate_routing_params

_BIC_RE = re.compile(r"^[A-Z0-9]{8}([A-Z0-9]{3})?$")
_VALID_CHARGE_BEARERS = frozenset({"SLEV", "DEBT", "CRED", "SHAR"})


class SwiftValidationError(Exception):
    def __init__(self, message: str, *, field: str | None = None) -> None:
        self.message = message
        self.field = field
        super().__init__(message)


def validate_bic(bic: str, *, field: str = "beneficiary_bic") -> str:
    """Validate and normalize beneficiary/correspondent BIC (8 or 11 alphanumeric)."""
    normalized = bic.strip().upper()
    if not _BIC_RE.match(normalized):
        raise SwiftValidationError(
            "BIC/SWIFT code must be 8 or 11 alphanumeric characters.",
            field=field,
        )
    try:
        validate_routing_params(ROUTING_SWIFT, {"bic": normalized})
    except RoutingValidationError as exc:
        raise SwiftValidationError(exc.message, field=field) from exc
    return normalized


def validate_charge_bearer(value: str | None) -> str:
    bearer = (value or "SLEV").upper()
    if bearer not in _VALID_CHARGE_BEARERS:
        raise SwiftValidationError(
            f"charge_bearer must be one of {sorted(_VALID_CHARGE_BEARERS)}.",
            field="charge_bearer",
        )
    return bearer
