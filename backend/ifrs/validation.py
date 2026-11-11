"""
IFRS transaction validation (Req 22.7).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ifrs.accounts import LEASE_LIABILITY_ACCOUNT, REVENUE_ACCOUNT, ROU_ASSET_ACCOUNT


@dataclass
class ValidationResult:
    valid: bool
    standard_reference: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "standard_reference": self.standard_reference,
            "message": self.message,
        }


def validate_ifrs_transaction(entries: list[dict[str, Any]]) -> ValidationResult:
    """Validate voucher entries against enforced IFRS rules."""
    if not entries:
        return ValidationResult(
            valid=False,
            standard_reference="IFRS General",
            message="Voucher must contain entries.",
        )

    codes = {e.get("account_code") for e in entries}

    # IFRS 16: lease liability credit requires matching ROU debit
    if LEASE_LIABILITY_ACCOUNT in codes and ROU_ASSET_ACCOUNT not in codes:
        lease_credits = sum(
            float(e.get("credit_amount", 0))
            for e in entries
            if e.get("account_code") == LEASE_LIABILITY_ACCOUNT
        )
        if lease_credits > 0:
            return ValidationResult(
                valid=False,
                standard_reference="IFRS 16",
                message="Lease liability recognition requires a corresponding right-of-use asset entry (IFRS 16).",
            )

    # IFRS 15: revenue credit without receivable/debit counterpart
    if REVENUE_ACCOUNT in codes:
        revenue_credits = sum(
            float(e.get("credit_amount", 0))
            for e in entries
            if e.get("account_code") == REVENUE_ACCOUNT
        )
        total_debits = sum(float(e.get("debit_amount", 0)) for e in entries)
        if revenue_credits > 0 and total_debits < revenue_credits:
            return ValidationResult(
                valid=False,
                standard_reference="IFRS 15",
                message="Revenue recognition requires an equal debit entry (IFRS 15).",
            )

    # IFRS 9: negative fair value adjustment on asset without loss account
    for entry in entries:
        code = entry.get("account_code", "")
        if code.startswith("151") and float(entry.get("credit_amount", 0)) > 0:
            has_loss = any(
                e.get("account_code", "").startswith("570")
                for e in entries
                if float(e.get("debit_amount", 0)) > 0
            )
            if not has_loss:
                return ValidationResult(
                    valid=False,
                    standard_reference="IFRS 9",
                    message="Fair value decreases must be recognized in profit or loss (IFRS 9).",
                )

    debits = sum(float(e.get("debit_amount", 0)) for e in entries)
    credits = sum(float(e.get("credit_amount", 0)) for e in entries)
    if abs(debits - credits) > 0.0001:
        return ValidationResult(
            valid=False,
            standard_reference="IFRS General",
            message="Voucher entries must balance under IFRS double-entry rules.",
        )

    return ValidationResult(valid=True, message="IFRS validation passed.")
