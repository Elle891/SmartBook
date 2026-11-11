"""
Pure balance/running-balance helpers for ledger queries and materialization.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

DEBIT_NORMAL_TYPES = frozenset({"Asset", "Expense"})

# Req 14.3 / 14.4 — cash type 1010, bank type 1020 (also CAS template codes)
CASH_ACCOUNT_CODES = frozenset({"1001"})
BANK_ACCOUNT_CODES = frozenset({"1002"})
CASH_CODE_PREFIX = "1010"
BANK_CODE_PREFIX = "1020"


def to_decimal(value: float | Decimal | int | str) -> Decimal:
    return Decimal(str(value))


def is_debit_normal(account_type: str) -> bool:
    return account_type in DEBIT_NORMAL_TYPES


def net_change(account_type: str, debit: Decimal, credit: Decimal) -> Decimal:
    """Signed movement toward closing balance for the account's normal side."""
    if is_debit_normal(account_type):
        return debit - credit
    return credit - debit


def compute_running_balance(
    previous_balance: Decimal,
    account_type: str,
    debit: Decimal,
    credit: Decimal,
) -> Decimal:
    return previous_balance + net_change(account_type, debit, credit)


def compute_closing_balance(
    opening: Decimal,
    total_debits: Decimal,
    total_credits: Decimal,
    account_type: str,
) -> Decimal:
    return opening + net_change(account_type, total_debits, total_credits)


def is_cash_account_code(account_code: str) -> bool:
    return account_code.startswith(CASH_CODE_PREFIX) or account_code in CASH_ACCOUNT_CODES


def is_bank_account_code(account_code: str) -> bool:
    return account_code.startswith(BANK_CODE_PREFIX) or account_code in BANK_ACCOUNT_CODES


def group_subsidiary_entries(
    entries: list[dict[str, Any]],
    dimension: str,
) -> list[dict[str, Any]]:
    """Group ledger rows by auxiliary dimension value (Req 14.2)."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in entries:
        aux = row.get("aux_dimension_values") or {}
        dim_value = str(aux.get(dimension) or "(none)")
        groups[dim_value].append(row)

    return [
        {
            "dimension": dimension,
            "dimension_value": value,
            "entries": sorted(
                items,
                key=lambda r: (r.get("entry_date"), r.get("voucher_number", 0)),
            ),
        }
        for value, items in sorted(groups.items(), key=lambda x: x[0])
    ]
