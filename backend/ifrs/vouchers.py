"""
IFRS voucher entry builders.
"""

from __future__ import annotations

from decimal import Decimal

from ifrs.accounts import (
    ACCUMULATED_IMPAIRMENT_ACCOUNT,
    FAIR_VALUE_GAIN_ACCOUNT,
    FAIR_VALUE_LOSS_ACCOUNT,
    FINANCIAL_ASSET_ACCOUNT,
    IMPAIRMENT_LOSS_ACCOUNT,
    LEASE_LIABILITY_ACCOUNT,
    RECEIVABLE_ACCOUNT,
    REVENUE_ACCOUNT,
    ROU_ASSET_ACCOUNT,
)


def build_fair_value_entries(
    *,
    account_code: str,
    adjustment_amount: float,
) -> list[dict]:
    amount = abs(Decimal(str(adjustment_amount)))
    if adjustment_amount >= 0:
        return [
            {
                "account_code": account_code or FINANCIAL_ASSET_ACCOUNT,
                "debit_amount": float(amount),
                "credit_amount": 0,
                "description": "IFRS 9 fair value adjustment",
            },
            {
                "account_code": FAIR_VALUE_GAIN_ACCOUNT,
                "debit_amount": 0,
                "credit_amount": float(amount),
                "description": "IFRS 9 fair value gain",
            },
        ]
    return [
        {
            "account_code": FAIR_VALUE_LOSS_ACCOUNT,
            "debit_amount": float(amount),
            "credit_amount": 0,
            "description": "IFRS 9 fair value loss",
        },
        {
            "account_code": account_code or FINANCIAL_ASSET_ACCOUNT,
            "debit_amount": 0,
            "credit_amount": float(amount),
            "description": "IFRS 9 fair value adjustment",
        },
    ]


def build_rou_initial_recognition_entries(*, amount: float) -> list[dict]:
    return [
        {
            "account_code": ROU_ASSET_ACCOUNT,
            "debit_amount": amount,
            "credit_amount": 0,
            "description": "IFRS 16 right-of-use asset initial recognition",
        },
        {
            "account_code": LEASE_LIABILITY_ACCOUNT,
            "debit_amount": 0,
            "credit_amount": amount,
            "description": "IFRS 16 lease liability initial recognition",
        },
    ]


def build_revenue_recognition_entries(*, amount: float, description: str) -> list[dict]:
    return [
        {
            "account_code": RECEIVABLE_ACCOUNT,
            "debit_amount": amount,
            "credit_amount": 0,
            "description": description,
        },
        {
            "account_code": REVENUE_ACCOUNT,
            "debit_amount": 0,
            "credit_amount": amount,
            "description": description,
        },
    ]


def build_impairment_entries(*, loss_amount: float, asset_account: str) -> list[dict]:
    return [
        {
            "account_code": IMPAIRMENT_LOSS_ACCOUNT,
            "debit_amount": loss_amount,
            "credit_amount": 0,
            "description": "IAS 36 impairment loss",
        },
        {
            "account_code": ACCUMULATED_IMPAIRMENT_ACCOUNT,
            "debit_amount": 0,
            "credit_amount": loss_amount,
            "description": f"IAS 36 impairment — asset {asset_account}",
        },
    ]


def entries_balanced(entries: list[dict]) -> bool:
    debits = sum(e["debit_amount"] for e in entries)
    credits = sum(e["credit_amount"] for e in entries)
    return abs(debits - credits) < 0.0001
