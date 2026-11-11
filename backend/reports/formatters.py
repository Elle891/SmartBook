"""
Currency formatting for reports (Req 9.10).
"""

from __future__ import annotations

from decimal import Decimal

CURRENCY_LOCALES = {
    "CNY": {"symbol": "¥", "decimals": 2},
    "USD": {"symbol": "$", "decimals": 2},
    "EUR": {"symbol": "€", "decimals": 2},
    "GBP": {"symbol": "£", "decimals": 2},
    "HKD": {"symbol": "HK$", "decimals": 2},
}

# Simplified static FX for report_currency override (Req 9.11)
FX_TO_CNY = {
    "CNY": Decimal("1"),
    "USD": Decimal("7.25"),
    "EUR": Decimal("7.85"),
    "GBP": Decimal("9.10"),
    "HKD": Decimal("0.93"),
}


def format_amount(amount: float | Decimal, currency: str) -> str:
    locale = CURRENCY_LOCALES.get(currency, {"symbol": currency + " ", "decimals": 2})
    value = Decimal(str(amount)).quantize(Decimal("0.01"))
    symbol = locale["symbol"]
    return f"{symbol}{value:,.2f}"


def convert_amount(
    amount: float | Decimal,
    *,
    from_currency: str,
    to_currency: str,
) -> float:
    if from_currency == to_currency:
        return float(amount)
    from_rate = FX_TO_CNY.get(from_currency, Decimal("1"))
    to_rate = FX_TO_CNY.get(to_currency, Decimal("1"))
    cny = Decimal(str(amount)) * from_rate
    return float((cny / to_rate).quantize(Decimal("0.01")))
