"""
Payroll module FastAPI router.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_PAYROLL, require_permission
from payroll import service
from platform.db_router import get_tenant_db
from schemas.payroll import EmployeeResponse
from schemas.payroll_api import (
    AccruePayrollRequest,
    AccruePayrollResponse,
    DistributePayslipsRequest,
    DistributePayslipsResponse,
    EmployeeCreateExtended,
    PayrollAdjustmentCreate,
    PayrollAdjustmentResponse,
    PayrollSettingsResponse,
    PayrollSettingsUpdate,
    PayslipResponse,
)

router = APIRouter(prefix="/account-sets", tags=["payroll"])

TenantDB = AsyncSession  # injected via Depends(get_tenant_db)


def _user_id(user: dict[str, Any]) -> str:
    return user.get("user_id") or user.get("sub", "")


def _account_set_id_from_user(user: dict[str, Any], path_id: str) -> str:
    jwt_account_set_id = user.get("account_set_id", "")
    if jwt_account_set_id and jwt_account_set_id != path_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_set_id in path does not match the active Account Set in your session.",
        )
    return path_id


@router.get("/{account_set_id}/payroll/settings", response_model=PayrollSettingsResponse)
async def api_get_payroll_settings(
    account_set_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PAYROLL)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    settings = await service.get_or_create_settings(db, aid)
    return PayrollSettingsResponse(account_set_id=settings.account_set_id, rates=settings.rates)


@router.put("/{account_set_id}/payroll/settings", response_model=PayrollSettingsResponse)
async def api_update_payroll_settings(
    account_set_id: uuid.UUID,
    body: PayrollSettingsUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PAYROLL)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    settings = await service.update_settings(db, account_set_id=aid, rates=body.rates)
    return PayrollSettingsResponse(account_set_id=settings.account_set_id, rates=settings.rates)


@router.post(
    "/{account_set_id}/payroll/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_register_employee(
    account_set_id: uuid.UUID,
    body: EmployeeCreateExtended,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PAYROLL)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.register_employee(
        db,
        account_set_id=aid,
        name=body.name,
        department=body.department,
        position=body.position,
        base_salary=body.base_salary,
        email=body.email,
        mobile=body.mobile,
    )


@router.get("/{account_set_id}/payroll/employees", response_model=list[EmployeeResponse])
async def api_list_employees(
    account_set_id: uuid.UUID,
    department: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PAYROLL)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.list_employees(db, account_set_id=aid, department=department)


@router.get("/{account_set_id}/payroll/departments", response_model=list[str])
async def api_list_departments(
    account_set_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PAYROLL)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.list_departments(db, account_set_id=aid)


@router.post(
    "/{account_set_id}/payroll/adjustments",
    response_model=PayrollAdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_record_adjustment(
    account_set_id: uuid.UUID,
    body: PayrollAdjustmentCreate,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PAYROLL)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    adj = await service.record_adjustment(
        db,
        account_set_id=aid,
        employee_id=str(body.employee_id),
        period_code=body.period_code,
        adjustment_type=body.adjustment_type,
        amount=body.amount,
        description=body.description,
    )
    return PayrollAdjustmentResponse(
        id=adj.id,
        account_set_id=adj.account_set_id,
        employee_id=adj.employee_id,
        period_code=adj.period_code,
        adjustment_type=adj.adjustment_type,
        amount=float(adj.amount),
        description=adj.description,
    )


@router.post(
    "/{account_set_id}/payroll/accrue",
    response_model=AccruePayrollResponse,
)
async def api_accrue_payroll(
    account_set_id: uuid.UUID,
    body: AccruePayrollRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PAYROLL)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.accrue_payroll(
        db,
        account_set_id=aid,
        period_code=body.period_code,
        user_id=_user_id(user),
    )


@router.get(
    "/{account_set_id}/payroll/payslips/{period_code}",
    response_model=list[PayslipResponse],
)
async def api_generate_payslips(
    account_set_id: uuid.UUID,
    period_code: str,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PAYROLL)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.generate_payslips(
        db, account_set_id=aid, period_code=period_code
    )


@router.post(
    "/{account_set_id}/payroll/payslips/{period_code}/distribute",
    response_model=DistributePayslipsResponse,
)
async def api_distribute_payslips(
    account_set_id: uuid.UUID,
    period_code: str,
    body: DistributePayslipsRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PAYROLL)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await service.distribute_payslips(
        db,
        account_set_id=aid,
        period_code=period_code,
        channel=body.channel,
    )


@router.post(
    "/{account_set_id}/payroll/payslips/{period_code}/distribute-async",
    status_code=status.HTTP_202_ACCEPTED,
)
async def api_distribute_payslips_async(
    account_set_id: uuid.UUID,
    period_code: str,
    body: DistributePayslipsRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_PAYROLL)),
):
    from app.tasks import distribute_payslips_task

    task = distribute_payslips_task.delay(
        account_set_id=str(account_set_id),
        period_code=period_code,
        channel=body.channel,
    )
    return {"task_id": task.id, "status": "accepted"}
