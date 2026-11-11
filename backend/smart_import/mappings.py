"""
Keyword-based account mapping rules for smart import (Req 19.4).
"""

from __future__ import annotations

from dataclasses import dataclass

BANK_ACCOUNT = "1001"
DEFAULT_REVENUE_ACCOUNT = "6001"
DEFAULT_EXPENSE_ACCOUNT = "6602"

DIRECTION_INFLOW = "Inflow"
DIRECTION_OUTFLOW = "Outflow"


@dataclass(frozen=True)
class AccountSuggestion:
    debit_account: str
    credit_account: str
    matched_keyword: str | None
    confidence: float


# (keywords, account_code for the non-bank side)
_INFLOW_RULES: list[tuple[tuple[str, ...], str]] = [
    (("销售收入", "营业收入", "收款", "收入", "revenue", "interest income"), "6001"),
    (("退款", "refund"), "6051"),
    (("贷款", "借款", "loan"), "2001"),
]

_OUTFLOW_RULES: list[tuple[tuple[str, ...], str]] = [
    (("工资", "薪酬", "salary", "payroll"), "2211"),
    (("租金", "房租", "rent"), "6602"),
    (("水电", "utility", "utilities", "电费", "水费"), "6602"),
    (("采购", "货款", "purchase", "供应商"), "2202"),
    (("手续费", "fee", "银行收费"), "6603"),
    (("利息", "interest"), "6603"),
    (("税费", "tax", "增值税"), "2221"),
    (("报销", "差旅", "travel"), "6602"),
]


def _match_rule(text: str, rules: list[tuple[tuple[str, ...], str]]) -> tuple[str | None, str | None]:
    lowered = text.lower()
    for keywords, account in rules:
        for kw in keywords:
            if kw.lower() in lowered:
                return account, kw
    return None, None


def suggest_account_mapping(
    *,
    direction: str,
    counterparty: str,
    description: str,
    bank_account: str = BANK_ACCOUNT,
) -> AccountSuggestion:
    """Suggest debit/credit accounts from description and counterparty."""
    text = f"{counterparty} {description}".strip()
    if direction == DIRECTION_INFLOW:
        account, keyword = _match_rule(text, _INFLOW_RULES)
        account = account or DEFAULT_REVENUE_ACCOUNT
        return AccountSuggestion(
            debit_account=bank_account,
            credit_account=account,
            matched_keyword=keyword,
            confidence=0.85 if keyword else 0.5,
        )

    account, keyword = _match_rule(text, _OUTFLOW_RULES)
    account = account or DEFAULT_EXPENSE_ACCOUNT
    return AccountSuggestion(
        debit_account=account,
        credit_account=bank_account,
        matched_keyword=keyword,
        confidence=0.85 if keyword else 0.5,
    )


def build_voucher_entries(
    *,
    debit_account: str,
    credit_account: str,
    amount: float,
    description: str,
) -> list[dict]:
    """Balanced two-line voucher entries for an imported transaction."""
    return [
        {
            "account_code": debit_account,
            "debit_amount": amount,
            "credit_amount": 0,
            "description": description,
        },
        {
            "account_code": credit_account,
            "debit_amount": 0,
            "credit_amount": amount,
            "description": description,
        },
    ]
