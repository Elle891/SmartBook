"""
Payroll module service.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.payroll import Employee, PayrollLine, PayrollRun
from models.payroll_settings import PayrollAdjustment, PayrollSettings, PayslipDistributionLog
from payroll.calculations import (
    DEFAULT_PAYROLL_RATES,
    build_payroll_voucher_entries,
    build_payslip,
    calculate_gross_salary,
    calculate_payroll_deductions,
    to_decimal,
)
from period_end.periods import assert_period_open
from voucher.service import create_voucher

logger = logging.getLogger(__name__)

RUN_STATUS_DRAFT = "Draft"
RUN_STATUS_CONFIRMED = "Confirmed"

# CAS default accounts for payroll voucher
SALARY_EXPENSE_ACCOUNT = "6602"
PAYABLE_ACCOUNT = "2202"


async def get_or_create_settings(
    db: AsyncSession, account_set_id: str
) -> PayrollSettings:
    result = await db.execute(
        select(PayrollSettings).where(PayrollSettings.account_set_id == account_set_id)
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = PayrollSettings(
            account_set_id=account_set_id,
            rates=dict(DEFAULT_PAYROLL_RATES),
        )
        db.add(settings)
        await db.flush()
    return settings


async def update_settings(
    db: AsyncSession,
    *,
    account_set_id: str,
    rates: dict[str, float],
) -> PayrollSettings:
    settings = await get_or_create_settings(db, account_set_id)
    merged = {**DEFAULT_PAYROLL_RATES, **settings.rates, **rates}
    settings.rates = merged
    await db.flush()
    return settings


async def register_employee(
    db: AsyncSession,
    *,
    account_set_id: str,
    name: str,
    department: str,
    position: str,
    base_salary: float,
    email: str | None = None,
    mobile: str | None = None,
) -> Employee:
    """Register employee (Req 17.1)."""
    employee = Employee(
        account_set_id=account_set_id,
        name=name,
        department=department,
        position=position,
        base_salary=base_salary,
        email=email,
        mobile=mobile,
        is_active=True,
    )
    db.add(employee)
    await db.flush()
    return employee


async def list_employees(
    db: AsyncSession,
    *,
    account_set_id: str,
    department: str | None = None,
    active_only: bool = True,
) -> list[Employee]:
    stmt = select(Employee).where(Employee.account_set_id == account_set_id)
    if department:
        stmt = stmt.where(Employee.department == department)
    if active_only:
        stmt = stmt.where(Employee.is_active.is_(True))
    stmt = stmt.order_by(Employee.department, Employee.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_departments(db: AsyncSession, *, account_set_id: str) -> list[str]:
    """Distinct departments for organizing employees (Req 17.2)."""
    result = await db.execute(
        select(Employee.department)
        .where(
            Employee.account_set_id == account_set_id,
            Employee.is_active.is_(True),
        )
        .distinct()
        .order_by(Employee.department)
    )
    return [row[0] for row in result.all() if row[0]]


async def record_adjustment(
    db: AsyncSession,
    *,
    account_set_id: str,
    employee_id: str,
    period_code: str,
    adjustment_type: str,
    amount: float,
    description: str = "",
) -> PayrollAdjustment:
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.account_set_id == account_set_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")

    adj = PayrollAdjustment(
        account_set_id=account_set_id,
        employee_id=employee_id,
        period_code=period_code,
        adjustment_type=adjustment_type,
        amount=amount,
        description=description,
    )
    db.add(adj)
    await db.flush()
    return adj


async def _adjustments_for_employee(
    db: AsyncSession,
    account_set_id: str,
    employee_id: str,
    period_code: str,
) -> list[Decimal]:
    result = await db.execute(
        select(PayrollAdjustment.amount).where(
            PayrollAdjustment.account_set_id == account_set_id,
            PayrollAdjustment.employee_id == employee_id,
            PayrollAdjustment.period_code == period_code,
        )
    )
    return [to_decimal(row[0]) for row in result.all()]


async def accrue_payroll(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    user_id: str,
    voucher_date: date | None = None,
) -> dict[str, Any]:
    """Accrue payroll, compute deductions, and create voucher (Req 17.3–17.5)."""
    await assert_period_open(db, account_set_id, period_code)

    existing = await db.execute(
        select(PayrollRun).where(
            PayrollRun.account_set_id == account_set_id,
            PayrollRun.period_code == period_code,
            PayrollRun.status == RUN_STATUS_CONFIRMED,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payroll for period {period_code} is already confirmed.",
        )

    draft_result = await db.execute(
        select(PayrollRun.id).where(
            PayrollRun.account_set_id == account_set_id,
            PayrollRun.period_code == period_code,
            PayrollRun.status == RUN_STATUS_DRAFT,
        )
    )
    for (draft_id,) in draft_result.all():
        await db.execute(
            delete(PayrollLine).where(PayrollLine.payroll_run_id == draft_id)
        )
    await db.execute(
        delete(PayrollRun).where(
            PayrollRun.account_set_id == account_set_id,
            PayrollRun.period_code == period_code,
            PayrollRun.status == RUN_STATUS_DRAFT,
        )
    )

    settings = await get_or_create_settings(db, account_set_id)
    employees = await list_employees(db, account_set_id=account_set_id)

    if not employees:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No active employees to accrue payroll.",
        )

    run = PayrollRun(
        account_set_id=account_set_id,
        period_code=period_code,
        status=RUN_STATUS_DRAFT,
    )
    db.add(run)
    await db.flush()

    total_gross = Decimal("0")
    total_net = Decimal("0")
    total_employee_ded = Decimal("0")
    total_employer = Decimal("0")
    lines: list[PayrollLine] = []

    for emp in employees:
        adjustments = await _adjustments_for_employee(
            db, account_set_id, str(emp.id), period_code
        )
        gross = calculate_gross_salary(to_decimal(emp.base_salary), adjustments)
        calc = calculate_payroll_deductions(gross, settings.rates)

        line = PayrollLine(
            payroll_run_id=run.id,
            employee_id=emp.id,
            gross_salary=float(gross),
            deductions=calc["employee_deductions"],
            net_salary=calc["net_salary"],
            payslip_sent=False,
        )
        db.add(line)
        lines.append(line)

        total_gross += gross
        total_net += to_decimal(calc["net_salary"])
        total_employee_ded += to_decimal(calc["total_employee_deductions"])
        total_employer += to_decimal(calc["total_employer_contributions"])

    await db.flush()

    entries = build_payroll_voucher_entries(
        total_gross=total_gross,
        total_net=total_net,
        total_employee_deductions=total_employee_ded,
        total_employer_contributions=total_employer,
        salary_expense_account=SALARY_EXPENSE_ACCOUNT,
        payable_account=PAYABLE_ACCOUNT,
    )

    vdate = voucher_date or date.today()
    voucher = await create_voucher(
        db,
        account_set_id=account_set_id,
        period_code=period_code,
        voucher_type="Payment",
        voucher_date=vdate,
        entries=entries,
        attachments=[],
        created_by_user_id=user_id,
    )

    run.status = RUN_STATUS_CONFIRMED
    run.voucher_id = voucher.id
    await db.flush()

    return {
        "message": "Payroll accrued and voucher created.",
        "payroll_run_id": str(run.id),
        "voucher_id": str(voucher.id),
        "period_code": period_code,
        "employee_count": len(lines),
        "total_gross": float(total_gross),
        "total_net": float(total_net),
    }


async def generate_payslips(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
) -> list[dict[str, Any]]:
    """Generate payslips for all employees in a payroll run (Req 17.6)."""
    result = await db.execute(
        select(PayrollRun).where(
            PayrollRun.account_set_id == account_set_id,
            PayrollRun.period_code == period_code,
            PayrollRun.status == RUN_STATUS_CONFIRMED,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No confirmed payroll run for period {period_code}.",
        )

    lines_result = await db.execute(
        select(PayrollLine, Employee)
        .join(Employee, PayrollLine.employee_id == Employee.id)
        .where(PayrollLine.payroll_run_id == run.id)
    )

    payslips: list[dict[str, Any]] = []
    settings = await get_or_create_settings(db, account_set_id)

    for line, emp in lines_result.all():
        gross = to_decimal(line.gross_salary)
        calc = calculate_payroll_deductions(gross, settings.rates)
        payslip = build_payslip(
            employee_id=str(emp.id),
            employee_name=emp.name,
            department=emp.department,
            position=emp.position,
            period_code=period_code,
            gross_salary=float(gross),
            deductions=line.deductions,
            net_salary=line.net_salary,
            employer_contributions=calc["employer_contributions"],
        )
        payslips.append(payslip)

    return payslips


async def distribute_payslip_to_employee(
    db: AsyncSession,
    *,
    account_set_id: str,
    payroll_run_id: str,
    employee_id: str,
    channel: str,
    payslip: dict[str, Any],
) -> PayslipDistributionLog:
    """Send one payslip via channel; log success or failure (Req 17.7, 17.8)."""
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.account_set_id == account_set_id,
        )
    )
    employee = result.scalar_one_or_none()
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")

    success = False
    failure_reason: str | None = None
    body = (
        f"Payslip {payslip['period_code']}: gross {payslip['gross_salary']}, "
        f"net {payslip['net_salary']}"
    )

    try:
        if channel == "email":
            if not employee.email:
                raise ValueError("Employee has no email address.")
            from notifications.email import send_email

            await send_email(
                to=employee.email,
                subject=f"Payslip — {payslip['period_code']}",
                body=body,
            )
        elif channel == "sms":
            if not employee.mobile:
                raise ValueError("Employee has no mobile number.")
            from notifications.sms import send_sms

            await send_sms(to=employee.mobile, message=body)
        elif channel == "wechat":
            if not employee.mobile:
                raise ValueError("Employee has no mobile for WeChat delivery.")
            # WeChat delivery stub — production integrates WeChat Work API
            logger.info("WeChat payslip stub sent to %s", employee.mobile)
        else:
            raise ValueError(f"Unsupported channel: {channel}")
        success = True
    except Exception as exc:  # noqa: BLE001
        failure_reason = str(exc)
        logger.warning(
            "Payslip distribution failed employee=%s channel=%s: %s",
            employee_id,
            channel,
            exc,
        )

    log = PayslipDistributionLog(
        account_set_id=account_set_id,
        payroll_run_id=payroll_run_id,
        employee_id=employee_id,
        channel=channel,
        success=success,
        failure_reason=failure_reason,
    )
    db.add(log)

    if success:
        line_result = await db.execute(
            select(PayrollLine).where(
                PayrollLine.payroll_run_id == payroll_run_id,
                PayrollLine.employee_id == employee_id,
            )
        )
        line = line_result.scalar_one_or_none()
        if line:
            line.payslip_sent = True

    await db.flush()
    return log


async def distribute_payslips(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
    channel: str,
) -> dict[str, Any]:
    """Distribute all payslips for a period via the given channel."""
    payslips = await generate_payslips(db, account_set_id=account_set_id, period_code=period_code)
    run_result = await db.execute(
        select(PayrollRun).where(
            PayrollRun.account_set_id == account_set_id,
            PayrollRun.period_code == period_code,
        )
    )
    run = run_result.scalar_one()

    succeeded: list[str] = []
    failed: list[dict[str, str]] = []

    for payslip in payslips:
        log = await distribute_payslip_to_employee(
            db,
            account_set_id=account_set_id,
            payroll_run_id=str(run.id),
            employee_id=payslip["employee_id"],
            channel=channel,
            payslip=payslip,
        )
        if log.success:
            succeeded.append(payslip["employee_id"])
        else:
            failed.append(
                {
                    "employee_id": payslip["employee_id"],
                    "reason": log.failure_reason or "Unknown error",
                }
            )

    return {
        "message": f"Distributed {len(succeeded)} of {len(payslips)} payslips via {channel}.",
        "succeeded": succeeded,
        "failed": failed,
    }
