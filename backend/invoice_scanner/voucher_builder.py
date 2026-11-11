"""
Invoice voucher entry builder (Req 20.5).
"""

from __future__ import annotations

from decimal import Decimal

EXPENSE_ACCOUNT = "6602"
INPUT_VAT_ACCOUNT = "2221"
PAYABLE_ACCOUNT = "2202"


def build_invoice_voucher_entries(
    *,
    amount_excl_tax: float,
    tax_amount: float,
    description: str,
    expense_account: str = EXPENSE_ACCOUNT,
    tax_account: str = INPUT_VAT_ACCOUNT,
    payable_account: str = PAYABLE_ACCOUNT,
) -> list[dict]:
    """Debit expense + input VAT; credit payable."""
    net = Decimal(str(amount_excl_tax))
    tax = Decimal(str(tax_amount))
    total = (net + tax).quantize(Decimal("0.01"))

    return [
        {
            "account_code": expense_account,
            "debit_amount": float(net),
            "credit_amount": 0,
            "description": description,
        },
        {
            "account_code": tax_account,
            "debit_amount": float(tax),
            "credit_amount": 0,
            "description": f"Input VAT — {description}",
        },
        {
            "account_code": payable_account,
            "debit_amount": 0,
            "credit_amount": float(total),
            "description": description,
        },
    ]


def merge_confirmed_data(
    extracted: dict,
    overrides: dict | None,
) -> dict:
    """Apply manual corrections from Finance_User (Req 20.4)."""
    merged = dict(extracted)
    if overrides:
        merged.update({k: v for k, v in overrides.items() if v is not None})
    return merged
