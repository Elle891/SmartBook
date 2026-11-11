"""
Payment routing method validation and bank capability matrix.
"""

from __future__ import annotations

import re
from typing import Any

from bank.errors import RoutingValidationError

ROUTING_DIRECT_DEBIT = "Direct_Debit"
ROUTING_ONLINE_BANKING = "Online_Banking_Transfer"
ROUTING_SWIFT = "SWIFT"
ROUTING_CNAPS = "CNAPS"
ROUTING_CIPS = "CIPS"
ROUTING_LOCAL_ACH = "Local_ACH"
ROUTING_INTERNAL = "Internal_Transfer"

ALL_ROUTING_METHODS = [
    ROUTING_DIRECT_DEBIT,
    ROUTING_ONLINE_BANKING,
    ROUTING_SWIFT,
    ROUTING_CNAPS,
    ROUTING_CIPS,
    ROUTING_LOCAL_ACH,
    ROUTING_INTERNAL,
]

_BIC_RE = re.compile(r"^[A-Z0-9]{8}([A-Z0-9]{3})?$")
_CNAPS_RE = re.compile(r"^\d{12}$")
_CIPS_RE = re.compile(r"^[A-Z0-9]{11}$")

# Supported methods per bank code (Req 25.2)
_BANK_SUPPORTED: dict[str, list[str]] = {
    "ICBC": [ROUTING_CNAPS, ROUTING_ONLINE_BANKING, ROUTING_INTERNAL, ROUTING_SWIFT],
    "BOC": [ROUTING_SWIFT, ROUTING_CNAPS, ROUTING_CIPS, ROUTING_ONLINE_BANKING],
    "CCB": [ROUTING_CNAPS, ROUTING_CIPS, ROUTING_ONLINE_BANKING, ROUTING_INTERNAL],
    "ABC": [ROUTING_CNAPS, ROUTING_LOCAL_ACH, ROUTING_ONLINE_BANKING],
    "DEFAULT": ALL_ROUTING_METHODS,
}


def get_bank_supported_methods(bank_code: str) -> list[str]:
    return list(_BANK_SUPPORTED.get(bank_code.upper(), _BANK_SUPPORTED["DEFAULT"]))


def validate_routing_params(routing_method: str, params: dict[str, Any]) -> None:
    """Validate routing parameters before persisting to Vault (Req 25.7)."""
    method = routing_method.strip()
    if method == ROUTING_SWIFT:
        bic = str(params.get("bic", "")).upper()
        if not _BIC_RE.match(bic):
            raise RoutingValidationError(
                "SWIFT BIC must be 8 or 11 alphanumeric characters.",
                details={"field": "bic", "standard_reference": "SWIFT"},
            )
        return

    if method == ROUTING_CNAPS:
        cnaps = str(params.get("cnaps_routing_number", ""))
        if not _CNAPS_RE.match(cnaps):
            raise RoutingValidationError(
                "CNAPS routing number must be exactly 12 digits.",
                details={"field": "cnaps_routing_number", "standard_reference": "CNAPS"},
            )
        return

    if method == ROUTING_CIPS:
        code = str(params.get("cips_participant_code", "")).upper()
        if not _CIPS_RE.match(code):
            raise RoutingValidationError(
                "CIPS participant code must be 11 alphanumeric characters.",
                details={"field": "cips_participant_code", "standard_reference": "CIPS"},
            )
        return

    if method in (ROUTING_DIRECT_DEBIT, ROUTING_ONLINE_BANKING, ROUTING_LOCAL_ACH, ROUTING_INTERNAL):
        if not str(params.get("account_identifier", "")).strip():
            raise RoutingValidationError(
                "account_identifier is required for this routing method.",
                details={"field": "account_identifier"},
            )
        return

    raise RoutingValidationError(
        f"Unsupported routing method: {routing_method}",
        details={"routing_method": routing_method},
    )


def routing_vault_path(connection_id: str, routing_method: str) -> str:
    return f"bank-routing/{connection_id}/{routing_method}"
