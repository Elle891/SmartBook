"""
Routing → settlement matrices and scope filtering.
"""

from __future__ import annotations

from bank.routing import (
    ROUTING_CIPS,
    ROUTING_CNAPS,
    ROUTING_DIRECT_DEBIT,
    ROUTING_INTERNAL,
    ROUTING_LOCAL_ACH,
    ROUTING_ONLINE_BANKING,
    ROUTING_SWIFT,
    get_bank_supported_methods,
)

SCOPE_DOMESTIC = "Domestic"
SCOPE_INTERNATIONAL = "International"

DOMESTIC_ROUTING_SETTLEMENT: dict[str, list[str]] = {
    ROUTING_DIRECT_DEBIT: ["Same_Day_Settlement", "Next_Day_Settlement"],
    ROUTING_ONLINE_BANKING: ["Real_Time_Gross_Settlement", "Batch_Settlement_T+1"],
    ROUTING_CNAPS: ["Real_Time_Settlement", "Scheduled_Settlement"],
    ROUTING_CIPS: ["Real_Time_Settlement", "End_Of_Day_Settlement"],
    ROUTING_LOCAL_ACH: ["Next_Day_Settlement", "Two_Day_Settlement"],
    ROUTING_INTERNAL: ["Immediate_Settlement"],
}

INTERNATIONAL_ROUTING_SETTLEMENT: dict[str, list[str]] = {
    ROUTING_SWIFT: [
        "Standard_Settlement_T+2",
        "Express_Settlement_T+1",
        "Same_Day_Value",
    ],
}

CNY_ONLY_ROUTING = {ROUTING_CNAPS, ROUTING_CIPS}


def settlement_methods_for_routing(
    routing_method: str,
    *,
    payment_scope: str,
) -> list[str]:
    if payment_scope == SCOPE_INTERNATIONAL:
        return list(INTERNATIONAL_ROUTING_SETTLEMENT.get(routing_method, []))
    return list(DOMESTIC_ROUTING_SETTLEMENT.get(routing_method, []))


def all_routing_settlement_pairs(*, payment_scope: str) -> list[tuple[str, str]]:
    matrix = (
        INTERNATIONAL_ROUTING_SETTLEMENT
        if payment_scope == SCOPE_INTERNATIONAL
        else DOMESTIC_ROUTING_SETTLEMENT
    )
    pairs: list[tuple[str, str]] = []
    for routing, settlements in matrix.items():
        for settlement in settlements:
            pairs.append((routing, settlement))
    return pairs


def validate_routing_settlement_pair(
    routing_method: str,
    settlement_method: str,
    *,
    payment_scope: str,
) -> None:
    """Raise ValueError when settlement is not valid for routing (Req 26.4)."""
    allowed = settlement_methods_for_routing(routing_method, payment_scope=payment_scope)
    if settlement_method not in allowed:
        raise ValueError(
            f"Settlement method '{settlement_method}' is not valid for routing '{routing_method}'."
        )


def filter_available_routing_methods(
    *,
    configured_available: set[str],
    bank_code: str,
    payment_scope: str,
    currency: str = "CNY",
    same_bank: bool | None = None,
) -> set[str]:
    """
    Pure routing filter used by getAvailableRoutingAndSettlement (Properties 21–22).
    """
    bank_supported = set(get_bank_supported_methods(bank_code))
    if payment_scope == SCOPE_INTERNATIONAL:
        return configured_available & bank_supported & {ROUTING_SWIFT}

    candidates = configured_available & bank_supported
    candidates -= {ROUTING_SWIFT}
    if same_bank is False:
        candidates -= {ROUTING_INTERNAL}
    if currency != "CNY":
        candidates -= CNY_ONLY_ROUTING
    return candidates


def build_routing_settlement_options(
    *,
    routing_methods: set[str],
    payment_scope: str,
    default_settlement_lookup: dict[str, str | None] | None = None,
    cutoff_lookup: dict[tuple[str, str], dict] | None = None,
) -> list[dict]:
    """Build routing/settlement option payloads for property tests and API."""
    defaults = default_settlement_lookup or {}
    cutoffs = cutoff_lookup or {}
    options: list[dict] = []
    for routing in sorted(routing_methods):
        settlements = settlement_methods_for_routing(routing, payment_scope=payment_scope)
        if not settlements:
            continue
        default_settlement = defaults.get(routing)
        settlement_details = []
        for sm in settlements:
            cutoff = cutoffs.get((routing, sm), {})
            settlement_details.append(
                {
                    "settlement_method": sm,
                    "is_default": sm == default_settlement,
                    **cutoff,
                }
            )
        options.append(
            {
                "routing_method": routing,
                "settlement_methods": settlement_details,
            }
        )
    return options
