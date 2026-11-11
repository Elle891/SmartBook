"""
Carry-forward account resolution per accounting standard (CAS / IFRS).
"""

from __future__ import annotations

from enum import Enum

# Carry-forward target types
CARRY_PROFIT_LOSS = "profit_loss"
CARRY_RETAINED_EARNINGS = "retained_earnings"
CARRY_DEPRECIATION_EXPENSE = "depreciation_expense"
CARRY_ACCUMULATED_DEPRECIATION = "accumulated_depreciation"


class ConfigurationError(Exception):
    """Unknown standard/type combination for carry-forward configuration."""


class MissingRetainedEarningsAccountError(Exception):
    """Chart of accounts lacks the retained earnings account for the standard."""


class PeriodClosedError(Exception):
    """The accounting period is closed and cannot accept changes."""


class UnapprovedVouchersError(Exception):
    """Month-end close blocked by unapproved vouchers."""

    def __init__(self, count: int) -> None:
        self.count = count
        super().__init__(f"{count} unapproved voucher(s) remain in the period.")


class Standard(str, Enum):
    CAS = "CAS"
    IFRS = "IFRS"


# Designated carry-forward accounts per standard
_CARRY_FORWARD_MAP: dict[str, dict[str, str]] = {
    Standard.CAS.value: {
        CARRY_PROFIT_LOSS: "3131",  # 本年利润
        CARRY_RETAINED_EARNINGS: "3141",  # 利润分配 — CAS retained earnings
        CARRY_DEPRECIATION_EXPENSE: "6602",  # 管理费用 — depreciation expense
        CARRY_ACCUMULATED_DEPRECIATION: "1601",  # contra via fixed asset (simplified until Task 14)
    },
    Standard.IFRS.value: {
        CARRY_PROFIT_LOSS: "3300",  # Retained Earnings — period result staging
        CARRY_RETAINED_EARNINGS: "3300",  # IAS 1 equity — retained earnings
        CARRY_DEPRECIATION_EXPENSE: "5600",  # Depreciation and Amortisation
        CARRY_ACCUMULATED_DEPRECIATION: "1510",  # Accumulated Depreciation — PP&E
    },
}

BALANCE_SHEET_TYPES = frozenset({"Asset", "Liability", "Equity"})
PL_TYPES = frozenset({"Revenue", "Expense"})


def get_carry_forward_account(standard: str, carry_type: str) -> str:
    """Resolve target account code for a carry-forward operation.

    Raises ConfigurationError when the standard/type pair is not configured.
    """
    standard_key = standard.upper()
    by_standard = _CARRY_FORWARD_MAP.get(standard_key)
    if by_standard is None:
        raise ConfigurationError(
            f"No carry-forward configuration for standard '{standard}'."
        )
    code = by_standard.get(carry_type)
    if code is None:
        raise ConfigurationError(
            f"No carry-forward account for standard '{standard}' type '{carry_type}'."
        )
    return code
