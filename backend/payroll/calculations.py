"""
Payroll calculation helpers (unit-tested).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

# Default 五险一金 rates (employee / employer fractions of gross salary)
DEFAULT_PAYROLL_RATES: dict[str, float] = {
    "pension_employee": 0.08,
    "pension_employer": 0.16,
    "medical_employee": 0.02,
    "medical_employer": 0.095,
    "unemployment_employee": 0.005,
    "unemployment_employer": 0.005,
    "housing_fund_employee": 0.12,
    "housing_fund_employer": 0.12,
}


def to_decimal(value: float | Decimal | int | str) -> Decimal:
    return Decimal(str(value))


def calculate_gross_salary(
    base_salary: Decimal,
    adjustments: list[Decimal],
) -> Decimal:
    """Gross = base salary + sum(adjustments) (Req 17.3)."""
    total = base_salary + sum(adjustments, Decimal("0"))
    return total.quantize(Decimal("0.01"))


def calculate_payroll_deductions(
    gross_salary: Decimal,
    rates: dict[str, float],
) -> dict[str, Any]:
    """Compute employee deductions and employer contributions (Req 17.4)."""
    merged = {**DEFAULT_PAYROLL_RATES, **rates}
    employee_deductions: dict[str, float] = {}
    employer_contributions: dict[str, float] = {}

    for key, rate in merged.items():
        amount = float((gross_salary * to_decimal(rate)).quantize(Decimal("0.01")))
        if key.endswith("_employee"):
            employee_deductions[key.replace("_employee", "")] = amount
        elif key.endswith("_employer"):
            employer_contributions[key.replace("_employer", "")] = amount

    total_employee = sum(employee_deductions.values())
    total_employer = sum(employer_contributions.values())
    net_salary = float((gross_salary - to_decimal(total_employee)).quantize(Decimal("0.01")))

    return {
        "employee_deductions": employee_deductions,
        "employer_contributions": employer_contributions,
        "total_employee_deductions": total_employee,
        "total_employer_contributions": total_employer,
        "net_salary": net_salary,
    }


def build_payslip(
    *,
    employee_id: str,
    employee_name: str,
    department: str,
    position: str,
    period_code: str,
    gross_salary: float,
    deductions: dict[str, Any],
    net_salary: float,
    employer_contributions: dict[str, float],
) -> dict[str, Any]:
    """Build a single payslip document (Req 17.6)."""
    return {
        "employee_id": employee_id,
        "employee_name": employee_name,
        "department": department,
        "position": position,
        "period_code": period_code,
        "gross_salary": gross_salary,
        "deductions": deductions,
        "employer_contributions": employer_contributions,
        "net_salary": net_salary,
    }


def build_payroll_voucher_entries(
    *,
    total_gross: Decimal,
    total_net: Decimal,
    total_employee_deductions: Decimal,
    total_employer_contributions: Decimal,
    salary_expense_account: str,
    payable_account: str,
) -> list[dict[str, Any]]:
    """Balanced payroll accrual voucher entries (Req 17.5)."""
    total_payable = total_net + total_employee_deductions + total_employer_contributions
    total_expense = total_gross + total_employer_contributions

    return [
        {
            "account_code": salary_expense_account,
            "debit_amount": float(total_expense),
            "credit_amount": 0,
            "description": "Payroll accrual — salary and employer contributions",
        },
        {
            "account_code": payable_account,
            "debit_amount": 0,
            "credit_amount": float(total_payable),
            "description": "Payroll accrual — wages and social insurance payable",
        },
    ]
