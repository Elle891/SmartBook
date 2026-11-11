"""
Financial statement builders from ledger aggregates.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from reports.formatters import convert_amount, format_amount
from reports.terminology import (
    BALANCE_SECTIONS,
    INCOME_SECTIONS,
    balance_section,
    report_title,
)

CASH_ACCOUNT_PREFIXES = ("1001", "1002", "1012", "1020")


def _sum_closing(rows: list[dict], account_types: set[str]) -> Decimal:
    total = Decimal("0")
    for row in rows:
        if row["account_type"] in account_types:
            total += Decimal(str(row["closing_balance"]))
    return total


def _sum_period_activity(rows: list[dict], account_types: set[str], *, revenue: bool) -> Decimal:
    total = Decimal("0")
    for row in rows:
        if row["account_type"] not in account_types:
            continue
        debits = Decimal(str(row["total_debits"]))
        credits = Decimal(str(row["total_credits"]))
        total += credits - debits if revenue else debits - credits
    return total


def build_balance_sheet(
    *,
    standard: str,
    rows: list[dict],
    currency: str,
    report_currency: str | None = None,
) -> dict[str, Any]:
    display_currency = report_currency or currency
    sections = BALANCE_SECTIONS[standard]
    line_items = []
    for key, account_types in (
        ("assets", {"Asset"}),
        ("liabilities", {"Liability"}),
        ("equity", {"Equity"}),
    ):
        amount = _sum_closing(rows, account_types)
        if report_currency and report_currency != currency:
            amount = Decimal(str(convert_amount(amount, from_currency=currency, to_currency=report_currency)))
        line_items.append(
            {
                "section": balance_section(standard, key),
                "section_key": key,
                "amount": float(amount),
                "amount_formatted": format_amount(amount, display_currency),
            }
        )
    total_assets = line_items[0]["amount"]
    total_liab_equity = line_items[1]["amount"] + line_items[2]["amount"]
    return {
        "title": report_title(standard, "balance_sheet"),
        "standard": standard,
        "currency": display_currency,
        "sections": sections,
        "line_items": line_items,
        "total_assets": total_assets,
        "total_liabilities_and_equity": total_liab_equity,
        "is_balanced": abs(total_assets - total_liab_equity) < 0.01,
    }


def build_income_statement(
    *,
    standard: str,
    rows: list[dict],
    currency: str,
    report_currency: str | None = None,
) -> dict[str, Any]:
    display_currency = report_currency or currency
    revenue = _sum_period_activity(rows, {"Revenue"}, revenue=True)
    expenses = _sum_period_activity(rows, {"Expense"}, revenue=False)
    net = revenue - expenses
    if report_currency and report_currency != currency:
        revenue = Decimal(str(convert_amount(revenue, from_currency=currency, to_currency=report_currency)))
        expenses = Decimal(str(convert_amount(expenses, from_currency=currency, to_currency=report_currency)))
        net = revenue - expenses

    sections = INCOME_SECTIONS[standard]
    return {
        "title": report_title(standard, "income_statement"),
        "standard": standard,
        "currency": display_currency,
        "line_items": [
            {
                "label": sections["revenue"],
                "amount": float(revenue),
                "amount_formatted": format_amount(revenue, display_currency),
            },
            {
                "label": sections["expenses"],
                "amount": float(expenses),
                "amount_formatted": format_amount(expenses, display_currency),
            },
            {
                "label": sections["net_profit"],
                "amount": float(net),
                "amount_formatted": format_amount(net, display_currency),
            },
        ],
        "net_profit": float(net),
    }


def _cash_rows(rows: list[dict]) -> list[dict]:
    return [
        r
        for r in rows
        if any(str(r["account_code"]).startswith(p) for p in CASH_ACCOUNT_PREFIXES)
    ]


def build_cash_flow_statement(
    *,
    standard: str,
    rows: list[dict],
    currency: str,
    method: str = "Indirect",
    report_currency: str | None = None,
) -> dict[str, Any]:
    display_currency = report_currency or currency
    cash_rows = _cash_rows(rows)
    operating = Decimal("0")
    investing = Decimal("0")
    financing = Decimal("0")
    for row in cash_rows:
        net = Decimal(str(row["total_debits"])) - Decimal(str(row["total_credits"]))
        operating += net

    net_income = _sum_period_activity(rows, {"Revenue"}, revenue=True) - _sum_period_activity(
        rows, {"Expense"}, revenue=False
    )

    if method == "Direct":
        presentation = [
            {"label": "Cash receipts from customers", "amount": float(max(operating, Decimal("0")))},
            {"label": "Cash paid to suppliers", "amount": float(min(operating, Decimal("0")))},
        ]
        net_change = operating
    else:
        presentation = [
            {"label": "Net profit", "amount": float(net_income)},
            {"label": "Adjustments for working capital", "amount": float(operating - net_income)},
        ]
        net_change = net_income + (operating - net_income)

    if report_currency and report_currency != currency:
        net_change = Decimal(
            str(convert_amount(net_change, from_currency=currency, to_currency=report_currency))
        )

    return {
        "title": report_title(standard, "cash_flow"),
        "standard": standard,
        "currency": display_currency,
        "method": method,
        "line_items": presentation,
        "net_change_in_cash": float(net_change),
        "net_change_formatted": format_amount(net_change, display_currency),
        "sections": {
            "operating": float(operating),
            "investing": float(investing),
            "financing": float(financing),
        },
    }


def build_account_summary_report(
    *,
    standard: str,
    rows: list[dict],
    currency: str,
    report_currency: str | None = None,
) -> dict[str, Any]:
    display_currency = report_currency or currency
    summary_rows = []
    for row in rows:
        summary_rows.append(
            {
                "account_code": row["account_code"],
                "account_name": row["account_name"],
                "total_debits": row["total_debits"],
                "total_credits": row["total_credits"],
                "total_debits_formatted": format_amount(row["total_debits"], display_currency),
                "total_credits_formatted": format_amount(row["total_credits"], display_currency),
                "closing_balance": row["closing_balance"],
            }
        )
    return {
        "title": report_title(standard, "account_summary"),
        "standard": standard,
        "currency": display_currency,
        "rows": summary_rows,
        "row_count": len(summary_rows),
    }


def build_disclosure_notes(*, standard: str, period_code: str) -> dict[str, Any]:
    return {
        "title": report_title(standard, "disclosure_notes"),
        "standard": standard,
        "period_code": period_code,
        "sections": [
            {
                "heading": "Accounting policies",
                "content": f"Financial statements prepared under {standard} for period {period_code}.",
            },
            {
                "heading": "Significant estimates",
                "content": "Management judgments applied to depreciation, impairment, and revenue recognition.",
            },
            {
                "heading": "Standard-specific disclosures",
                "content": "IFRS 15 revenue, IFRS 16 leases, and IFRS 9 financial instruments disclosures apply.",
            },
        ],
    }
