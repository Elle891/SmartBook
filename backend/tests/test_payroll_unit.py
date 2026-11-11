"""
Unit tests for Payroll module — salary, deductions, payslip generation.

_Requirements: 17.1–17.8 (Task 13.1)_
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from payroll.calculations import (
    DEFAULT_PAYROLL_RATES,
    build_payslip,
    calculate_gross_salary,
    calculate_payroll_deductions,
    build_payroll_voucher_entries,
)


class TestGrossSalary:
    def test_base_only(self):
        gross = calculate_gross_salary(Decimal("10000"), [])
        assert gross == Decimal("10000.00")

    def test_with_adjustments(self):
        gross = calculate_gross_salary(
            Decimal("10000"),
            [Decimal("500"), Decimal("-200")],
        )
        assert gross == Decimal("10300.00")


class TestDeductions:
    def test_employee_and_employer_components(self):
        gross = Decimal("10000")
        result = calculate_payroll_deductions(gross, DEFAULT_PAYROLL_RATES)

        assert "pension" in result["employee_deductions"]
        assert result["employee_deductions"]["pension"] == 800.0
        assert result["employer_contributions"]["pension"] == 1600.0
        assert result["total_employee_deductions"] > 0
        assert result["total_employer_contributions"] > 0
        assert result["net_salary"] == float(
            gross - Decimal(str(result["total_employee_deductions"]))
        )

    def test_custom_rates_override_defaults(self):
        gross = Decimal("10000")
        result = calculate_payroll_deductions(
            gross,
            {"pension_employee": 0.10, "pension_employer": 0.20},
        )
        assert result["employee_deductions"]["pension"] == 1000.0
        assert result["employer_contributions"]["pension"] == 2000.0


class TestPayrollVoucher:
    def test_voucher_entries_balance(self):
        entries = build_payroll_voucher_entries(
            total_gross=Decimal("10000"),
            total_net=Decimal("7500"),
            total_employee_deductions=Decimal("2500"),
            total_employer_contributions=Decimal("3000"),
            salary_expense_account="6602",
            payable_account="2202",
        )
        debits = sum(e["debit_amount"] for e in entries)
        credits = sum(e["credit_amount"] for e in entries)
        assert debits == credits
        assert debits == 13000.0


class TestPayslipGeneration:
    def test_build_payslip_structure(self):
        payslip = build_payslip(
            employee_id="emp-1",
            employee_name="Zhang San",
            department="Finance",
            position="Accountant",
            period_code="202501",
            gross_salary=10000.0,
            deductions={"pension": 800.0},
            net_salary=7500.0,
            employer_contributions={"pension": 1600.0},
        )
        assert payslip["employee_name"] == "Zhang San"
        assert payslip["period_code"] == "202501"
        assert payslip["net_salary"] == 7500.0
        assert payslip["deductions"]["pension"] == 800.0

    @pytest.mark.asyncio
    async def test_generate_payslips_requires_confirmed_run(self):
        from unittest.mock import AsyncMock, MagicMock

        from fastapi import HTTPException
        from payroll import service as pay_svc

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(HTTPException) as exc:
            await pay_svc.generate_payslips(
                db, account_set_id="as-1", period_code="202501"
            )
        assert exc.value.status_code == 404
