"""
Feature engineering for cash flow forecasting (Task 28).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import pandas as pd

CASH_ACCOUNT_PREFIXES = ("1001", "1002", "1020")


@dataclass(frozen=True)
class MonthlyCashFlowRow:
    period_code: str
    inflow: float
    outflow: float

    @property
    def net_cash_flow(self) -> float:
        return self.inflow - self.outflow


def _period_from_date(value: Any) -> str:
    if hasattr(value, "year") and hasattr(value, "month"):
        return f"{value.year}{value.month:02d}"
    text = str(value)
    return text.replace("-", "")[:6]


def aggregate_bank_transactions(rows: Sequence[Any]) -> dict[str, MonthlyCashFlowRow]:
    monthly: dict[str, dict[str, float]] = {}
    for row in rows:
        period = _period_from_date(getattr(row, "date", ""))
        bucket = monthly.setdefault(period, {"inflow": 0.0, "outflow": 0.0})
        amount = float(getattr(row, "amount", 0))
        direction = str(getattr(row, "direction", "")).lower()
        if direction == "inflow":
            bucket["inflow"] += amount
        else:
            bucket["outflow"] += amount
    return {
        period: MonthlyCashFlowRow(period_code=period, inflow=v["inflow"], outflow=v["outflow"])
        for period, v in monthly.items()
    }


def aggregate_ledger_entries(rows: Sequence[Any]) -> dict[str, dict[str, float]]:
    monthly: dict[str, dict[str, float]] = {}
    for row in rows:
        account_code = str(getattr(row, "account_code", ""))
        if not account_code.startswith(CASH_ACCOUNT_PREFIXES):
            continue
        period = str(getattr(row, "period_code", ""))
        bucket = monthly.setdefault(period, {"debits": 0.0, "credits": 0.0})
        bucket["debits"] += float(getattr(row, "debit_amount", 0))
        bucket["credits"] += float(getattr(row, "credit_amount", 0))
    return monthly


def build_monthly_cashflow_frame(
    bank_rows: Sequence[Any],
    ledger_rows: Sequence[Any],
) -> pd.DataFrame:
    """Merge bank transactions and ledger cash accounts into monthly features."""
    bank_monthly = aggregate_bank_transactions(bank_rows)
    ledger_monthly = aggregate_ledger_entries(ledger_rows)

    periods = sorted(set(bank_monthly) | set(ledger_monthly))
    records: list[dict[str, Any]] = []
    for period in periods:
        bank = bank_monthly.get(period)
        ledger = ledger_monthly.get(period, {"debits": 0.0, "credits": 0.0})
        inflow = (bank.inflow if bank else 0.0) + ledger["debits"]
        outflow = (bank.outflow if bank else 0.0) + ledger["credits"]
        records.append(
            {
                "period_code": period,
                "inflow": inflow,
                "outflow": outflow,
                "net_cash_flow": inflow - outflow,
            }
        )

    if not records:
        return pd.DataFrame(
            columns=[
                "period_code",
                "inflow",
                "outflow",
                "net_cash_flow",
                "month",
                "quarter",
                "is_year_end",
                "is_quarter_end",
                "lag_1",
                "lag_3",
                "lag_6",
                "mean_3m",
                "std_3m",
                "mean_6m",
            ]
        )

    df = pd.DataFrame(records).sort_values("period_code").reset_index(drop=True)
    return add_time_series_features(df)


def add_time_series_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add calendar, lag, and rolling features (Req 23.11)."""
    if df.empty:
        return df

    out = df.copy()
    out["month"] = out["period_code"].str[4:6].astype(int)
    out["quarter"] = ((out["month"] - 1) // 3 + 1).astype(int)
    out["is_year_end"] = (out["month"] == 12).astype(int)
    out["is_quarter_end"] = out["month"].isin([3, 6, 9, 12]).astype(int)

    net = out["net_cash_flow"]
    out["lag_1"] = net.shift(1)
    out["lag_3"] = net.shift(3)
    out["lag_6"] = net.shift(6)
    out["mean_3m"] = net.rolling(window=3, min_periods=1).mean()
    out["std_3m"] = net.rolling(window=3, min_periods=1).std().fillna(0.0)
    out["mean_6m"] = net.rolling(window=6, min_periods=1).mean()
    return out


def count_data_months(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    return int(df["period_code"].nunique())


def compute_ledger_net_cash_flow(balances: Sequence[Any]) -> float:
    """Property 16: net cash flow from cash/bank AccountBalance rows."""
    net = 0.0
    for balance in balances:
        code = str(getattr(balance, "account_code", ""))
        if code.startswith(CASH_ACCOUNT_PREFIXES):
            net += float(getattr(balance, "total_debits", 0)) - float(
                getattr(balance, "total_credits", 0)
            )
    return net
