"""
Fixed asset depreciation and disposal calculations (unit-tested).
"""

from __future__ import annotations

from decimal import Decimal

METHOD_STRAIGHT_LINE = "StraightLine"
METHOD_DECLINING_BALANCE = "DecliningBalance"

DEFAULT_DECLINING_MONTHLY_RATE = Decimal("0.02")


def to_decimal(value: float | Decimal | int | str) -> Decimal:
    return Decimal(str(value))


def straight_line_monthly(cost: Decimal, useful_life_months: int) -> Decimal:
    """Straight-line: cost / useful_life_months (Req 18.2)."""
    if useful_life_months <= 0:
        return Decimal("0")
    return (cost / Decimal(useful_life_months)).quantize(Decimal("0.0001"))


def declining_balance_monthly(net_book_value: Decimal, rate: Decimal) -> Decimal:
    """Declining-balance: net_book_value × rate (Req 18.2)."""
    if net_book_value <= 0 or rate <= 0:
        return Decimal("0")
    amount = (net_book_value * rate).quantize(Decimal("0.0001"))
    return min(amount, net_book_value)


def calculate_depreciation_amount(
    *,
    cost: Decimal,
    net_book_value: Decimal,
    useful_life_months: int,
    method: str,
    declining_balance_rate: Decimal | None = None,
) -> Decimal:
    """Monthly depreciation for one asset."""
    if method == METHOD_DECLINING_BALANCE:
        rate = declining_balance_rate or DEFAULT_DECLINING_MONTHLY_RATE
        return declining_balance_monthly(net_book_value, rate)
    return straight_line_monthly(cost, useful_life_months)


def disposal_gain_loss(net_book_value: Decimal, proceeds: Decimal) -> Decimal:
    """Gain (positive) or loss (negative) on disposal (Req 18.7)."""
    return (proceeds - net_book_value).quantize(Decimal("0.01"))


def build_disposal_voucher_entries(
    *,
    cost: Decimal,
    accumulated_depreciation: Decimal,
    net_book_value: Decimal,
    proceeds: Decimal,
    asset_account: str,
    accum_dep_account: str,
    cash_account: str,
    gain_account: str,
    loss_account: str,
) -> list[dict]:
    """Balanced disposal journal entries."""
    gain_loss = disposal_gain_loss(net_book_value, proceeds)
    entries: list[dict] = [
        {
            "account_code": cash_account,
            "debit_amount": float(proceeds),
            "credit_amount": 0,
            "description": "Asset disposal proceeds",
        },
        {
            "account_code": accum_dep_account,
            "debit_amount": float(accumulated_depreciation),
            "credit_amount": 0,
            "description": "Remove accumulated depreciation",
        },
        {
            "account_code": asset_account,
            "debit_amount": 0,
            "credit_amount": float(cost),
            "description": "Remove asset cost",
        },
    ]
    if gain_loss > 0:
        entries.append(
            {
                "account_code": gain_account,
                "debit_amount": 0,
                "credit_amount": float(gain_loss),
                "description": "Gain on asset disposal",
            }
        )
    elif gain_loss < 0:
        entries.append(
            {
                "account_code": loss_account,
                "debit_amount": float(abs(gain_loss)),
                "credit_amount": 0,
                "description": "Loss on asset disposal",
            }
        )
    return entries
