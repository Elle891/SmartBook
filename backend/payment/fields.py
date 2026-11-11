"""
ISO 20022 pain.001 field definitions and form rendering helpers.
"""

from __future__ import annotations

from payment.pain001 import MANDATORY_FIELDS
from payment.routing_matrix import (
    DOMESTIC_ROUTING_SETTLEMENT,
    INTERNATIONAL_ROUTING_SETTLEMENT,
    SCOPE_DOMESTIC,
    SCOPE_INTERNATIONAL,
    all_routing_settlement_pairs,
)

VISIBILITY_REQUIRED = "Required"
VISIBILITY_OPTIONAL = "Optional"
VISIBILITY_HIDDEN = "Hidden"

ALL_ISO_FIELDS: tuple[str, ...] = (
    "debtor_name",
    "debtor_account",
    "debtor_agent_bic",
    "creditor_name",
    "creditor_account",
    "creditor_agent_bic",
    "creditor_agent_name",
    "creditor_agent_address",
    "intermediary_agent_bic",
    "payment_currency",
    "instructed_amount",
    "exchange_rate",
    "value_date",
    "end_to_end_id",
    "payment_purpose_code",
    "remittance_information",
    "charge_bearer",
    "regulatory_reporting",
)

SWIFT_EXTRA_OPTIONAL = (
    "creditor_agent_bic",
    "creditor_agent_name",
    "creditor_agent_address",
    "intermediary_agent_bic",
)


class FieldConfigValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def enforce_mandatory_fields(field_configs: dict[str, str]) -> None:
    """Mandatory fields must remain Required (Req 28.7)."""
    for field in MANDATORY_FIELDS:
        visibility = field_configs.get(field, VISIBILITY_REQUIRED)
        if visibility != VISIBILITY_REQUIRED:
            raise FieldConfigValidationError(
                f"Field '{field}' must always be Required and cannot be {visibility}."
            )


def merge_with_mandatory_defaults(field_configs: dict[str, str]) -> dict[str, str]:
    merged = dict(field_configs)
    for field in MANDATORY_FIELDS:
        merged[field] = VISIBILITY_REQUIRED
    return merged


def render_form_fields(field_configs: dict[str, str]) -> list[str]:
    """
    Return fields shown on payment form: Required + Optional only (Property 24).
    """
    visible = [
        name
        for name, visibility in field_configs.items()
        if visibility in (VISIBILITY_REQUIRED, VISIBILITY_OPTIONAL)
    ]
    return sorted(visible)


def default_visibility_for_field(field_name: str, *, routing_method: str) -> str:
    if field_name in MANDATORY_FIELDS:
        return VISIBILITY_REQUIRED
    if routing_method == "SWIFT" and field_name in SWIFT_EXTRA_OPTIONAL:
        return VISIBILITY_OPTIONAL
    if field_name in ("debtor_name", "end_to_end_id", "remittance_information"):
        return VISIBILITY_OPTIONAL
    if field_name in ("exchange_rate", "regulatory_reporting", "charge_bearer"):
        return VISIBILITY_HIDDEN
    return VISIBILITY_OPTIONAL


def build_default_field_configs() -> list[tuple[str, str, str, str, str]]:
    """Return (scope, routing_method, settlement_method, field_name, visibility) rows."""
    configs: list[tuple[str, str, str, str, str]] = []
    for scope in (SCOPE_DOMESTIC, SCOPE_INTERNATIONAL):
        for routing, settlement in all_routing_settlement_pairs(payment_scope=scope):
            for field in ALL_ISO_FIELDS:
                visibility = default_visibility_for_field(field, routing_method=routing)
                configs.append((scope, routing, settlement, field, visibility))
    return configs
