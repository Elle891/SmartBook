"""
Tax filing report aggregation from ledger balances (Req 21.1, 21.2).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

TAX_TYPE_VAT = "VAT"
TAX_TYPE_CIT = "CIT"

# CAS account code prefixes for tax aggregation
VAT_OUTPUT_PREFIXES = ("22210102", "22210105", "222102")
VAT_INPUT_PREFIXES = ("22210101", "22210103")
CIT_EXPENSE_PREFIXES = ("660", "640", "670")
CIT_REVENUE_PREFIXES = ("600", "605", "630")


def _match_prefix(code: str, prefixes: tuple[str, ...]) -> bool:
    return any(code.startswith(p) for p in prefixes)


def _activity_amount(row: dict, *, revenue: bool) -> Decimal:
    debits = Decimal(str(row["total_debits"]))
    credits = Decimal(str(row["total_credits"]))
    if revenue:
        return credits - debits
    return debits - credits


def build_vat_report(rows: list[dict], *, period_code: str) -> dict[str, Any]:
    taxable_sales = Decimal("0")
    output_vat = Decimal("0")
    input_vat = Decimal("0")

    for row in rows:
        code = row["account_code"]
        debits = Decimal(str(row["total_debits"]))
        credits = Decimal(str(row["total_credits"]))
        if row["account_type"] == "Revenue" or code.startswith("600"):
            taxable_sales += _activity_amount(row, revenue=True)
        if _match_prefix(code, VAT_OUTPUT_PREFIXES):
            output_vat += credits
        elif _match_prefix(code, VAT_INPUT_PREFIXES):
            input_vat += debits

    vat_payable = max(output_vat - input_vat, Decimal("0"))
    lines = [
        {
            "line_id": "taxable_sales",
            "label": "Taxable sales",
            "amount": float(taxable_sales.quantize(Decimal("0.01"))),
            "editable": True,
        },
        {
            "line_id": "output_vat",
            "label": "Output VAT",
            "amount": float(output_vat.quantize(Decimal("0.01"))),
            "editable": True,
        },
        {
            "line_id": "input_vat",
            "label": "Input VAT",
            "amount": float(input_vat.quantize(Decimal("0.01"))),
            "editable": True,
        },
        {
            "line_id": "vat_payable",
            "label": "VAT payable",
            "amount": float(vat_payable.quantize(Decimal("0.01"))),
            "editable": False,
        },
    ]
    return {
        "tax_type": TAX_TYPE_VAT,
        "period_code": period_code,
        "title": "Value-Added Tax Filing Report",
        "line_items": lines,
        "summary": {"vat_payable": float(vat_payable.quantize(Decimal("0.01")))},
    }


def build_cit_report(rows: list[dict], *, period_code: str) -> dict[str, Any]:
    total_revenue = Decimal("0")
    total_expenses = Decimal("0")

    for row in rows:
        code = row["account_code"]
        if row["account_type"] == "Revenue" or _match_prefix(code, CIT_REVENUE_PREFIXES):
            total_revenue += _activity_amount(row, revenue=True)
        if row["account_type"] == "Expense" or _match_prefix(code, CIT_EXPENSE_PREFIXES):
            total_expenses += _activity_amount(row, revenue=False)

    taxable_income = total_revenue - total_expenses
    cit_rate = Decimal("0.25")
    cit_payable = max(taxable_income * cit_rate, Decimal("0"))

    lines = [
        {
            "line_id": "total_revenue",
            "label": "Total revenue",
            "amount": float(total_revenue.quantize(Decimal("0.01"))),
            "editable": True,
        },
        {
            "line_id": "total_expenses",
            "label": "Total expenses",
            "amount": float(total_expenses.quantize(Decimal("0.01"))),
            "editable": True,
        },
        {
            "line_id": "taxable_income",
            "label": "Taxable income",
            "amount": float(taxable_income.quantize(Decimal("0.01"))),
            "editable": False,
        },
        {
            "line_id": "cit_payable",
            "label": "Corporate income tax payable",
            "amount": float(cit_payable.quantize(Decimal("0.01"))),
            "editable": False,
        },
    ]
    return {
        "tax_type": TAX_TYPE_CIT,
        "period_code": period_code,
        "title": "Corporate Income Tax Filing Report",
        "line_items": lines,
        "summary": {
            "taxable_income": float(taxable_income.quantize(Decimal("0.01"))),
            "cit_payable": float(cit_payable.quantize(Decimal("0.01"))),
        },
    }


def apply_line_adjustment(report_data: dict[str, Any], line_id: str, value: float) -> dict[str, Any]:
    """Adjust a line item before submission (Req 21.3)."""
    updated = dict(report_data)
    items = [dict(item) for item in updated.get("line_items", [])]
    found = False
    for item in items:
        if item["line_id"] == line_id:
            if not item.get("editable", True):
                raise ValueError(f"Line item {line_id} is not editable.")
            item["amount"] = value
            item["adjusted"] = True
            found = True
            break
    if not found:
        raise ValueError(f"Line item {line_id} not found.")

    updated["line_items"] = items
    if updated.get("tax_type") == TAX_TYPE_VAT:
        output_vat = _line_amount(items, "output_vat")
        input_vat = _line_amount(items, "input_vat")
        vat_payable = max(output_vat - input_vat, 0.0)
        for item in items:
            if item["line_id"] == "vat_payable":
                item["amount"] = vat_payable
        updated["summary"] = {"vat_payable": vat_payable}
    elif updated.get("tax_type") == TAX_TYPE_CIT:
        revenue = _line_amount(items, "total_revenue")
        expenses = _line_amount(items, "total_expenses")
        taxable = revenue - expenses
        cit_payable = max(taxable * 0.25, 0.0)
        for item in items:
            if item["line_id"] == "taxable_income":
                item["amount"] = taxable
            if item["line_id"] == "cit_payable":
                item["amount"] = cit_payable
        updated["summary"] = {"taxable_income": taxable, "cit_payable": cit_payable}
    updated["line_items"] = items
    return updated


def _line_amount(items: list[dict], line_id: str) -> float:
    for item in items:
        if item["line_id"] == line_id:
            return float(item["amount"])
    return 0.0
