"""
Pure cashier calculation helpers (unit-tested).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def to_decimal(value: float | Decimal | int | str) -> Decimal:
    return Decimal(str(value))


def compute_functional_amount(
    amount: Decimal,
    *,
    foreign_amount: Decimal | None = None,
    exchange_rate: Decimal | None = None,
) -> Decimal:
    """Functional currency amount from foreign amount × rate (Req 16.6)."""
    if foreign_amount is not None and exchange_rate is not None:
        return (foreign_amount * exchange_rate).quantize(Decimal("0.0001"))
    return amount.quantize(Decimal("0.0001"))


def validate_transfer_balanced(
    income_amount: Decimal,
    expenditure_amount: Decimal,
) -> None:
    """Raise ValueError when income ≠ expenditure (Req 16.5)."""
    if income_amount != expenditure_amount:
        diff = abs(income_amount - expenditure_amount)
        raise ValueError(
            f"Transfer income ({income_amount}) must equal expenditure ({expenditure_amount}); "
            f"difference={diff}"
        )


def compute_fx_balance(
    transactions: list[dict[str, Any]],
    *,
    account_code: str,
    base_currency: str,
) -> dict[str, Any]:
    """Aggregate foreign and functional balances for an account (Req 16.7)."""
    foreign_total = Decimal("0")
    functional_total = Decimal("0")
    foreign_currency: str | None = None

    for txn in transactions:
        if txn.get("primary_account_code") != account_code:
            continue
        fc = txn.get("foreign_currency")
        if not fc or fc == base_currency:
            functional_total += to_decimal(txn.get("functional_amount", 0))
            continue
        foreign_currency = fc
        foreign_total += to_decimal(txn.get("foreign_amount") or 0)
        functional_total += to_decimal(txn.get("functional_amount", 0))

    effective_rate: float | None = None
    if foreign_total > 0:
        effective_rate = float((functional_total / foreign_total).quantize(Decimal("0.000001")))

    return {
        "account_code": account_code,
        "base_currency": base_currency,
        "foreign_currency": foreign_currency,
        "foreign_balance": float(foreign_total),
        "functional_balance": float(functional_total),
        "effective_exchange_rate": effective_rate,
    }


def build_reconciliation_report(
    *,
    account_code: str,
    system_balance: Decimal,
    physical_count: Decimal,
) -> dict[str, Any]:
    """Cash reconciliation discrepancy report (Req 16.8)."""
    discrepancy = physical_count - system_balance
    return {
        "account_code": account_code,
        "system_balance": float(system_balance),
        "physical_count": float(physical_count),
        "discrepancy": float(discrepancy),
        "is_balanced": discrepancy == 0,
        "message": (
            "Cash reconciliation balanced."
            if discrepancy == 0
            else f"Discrepancy of {discrepancy} detected (physical − system)."
        ),
    }
