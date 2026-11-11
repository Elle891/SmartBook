"""Period code helpers for monthly forecasting."""

from __future__ import annotations


def next_period_code(period_code: str) -> str:
    year = int(period_code[:4])
    month = int(period_code[4:6])
    if month == 12:
        return f"{year + 1}01"
    return f"{year}{month + 1:02d}"


def generate_future_period_codes(start_period: str, count: int) -> list[str]:
    codes: list[str] = []
    current = start_period
    for _ in range(count):
        codes.append(current)
        current = next_period_code(current)
    return codes


def period_sort_key(period_code: str) -> tuple[int, int]:
    return int(period_code[:4]), int(period_code[4:6])
