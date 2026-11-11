"""
Report Engine FastAPI router.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_REPORTS, require_permission
from platform.db_router import get_tenant_db
from reports import data_sources, service, templates
from reports.errors import MethodNotSupportedError, ReportError, StandardMismatchError
from reports.filters import ReportFilter
from schemas.reports_api import (
    ConnectionTestResponse,
    DataSourceCreateRequest,
    DataSourceResponse,
    ReportFilterRequest,
    ReportTemplateCreateRequest,
    ReportTemplatePublishRequest,
    ReportTemplateResponse,
)

router = APIRouter(prefix="/account-sets", tags=["reports"])

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


def _filters(body: ReportFilterRequest) -> ReportFilter:
    return ReportFilter(
        period_code=body.period_code,
        date_from=body.date_from,
        date_to=body.date_to,
        report_currency=body.report_currency,
        entity_id=body.entity_id,
        entity_group_id=body.entity_group_id,
        account_code=body.account_code,
        cash_flow_method=body.cash_flow_method,
    )


def _handle_report_error(exc: ReportError) -> HTTPException:
    code = status.HTTP_422_UNPROCESSABLE_ENTITY
    if isinstance(exc, StandardMismatchError):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(status_code=code, detail=exc.to_dict())


@router.post("/{account_set_id}/reports/balance-sheet")
async def api_balance_sheet(
    account_set_id: uuid.UUID,
    body: ReportFilterRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.generate_balance_sheet(
            db, account_set_id=aid, filters=_filters(body), user_id=_user_id(user)
        )
    except ReportError as exc:
        raise _handle_report_error(exc) from exc


@router.post("/{account_set_id}/reports/income-statement")
async def api_income_statement(
    account_set_id: uuid.UUID,
    body: ReportFilterRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.generate_income_statement(
            db, account_set_id=aid, filters=_filters(body), user_id=_user_id(user)
        )
    except ReportError as exc:
        raise _handle_report_error(exc) from exc


@router.post("/{account_set_id}/reports/cash-flow")
async def api_cash_flow(
    account_set_id: uuid.UUID,
    body: ReportFilterRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.generate_cash_flow_statement(
            db, account_set_id=aid, filters=_filters(body), user_id=_user_id(user)
        )
    except ReportError as exc:
        raise _handle_report_error(exc) from exc


@router.post("/{account_set_id}/reports/account-summary")
async def api_account_summary(
    account_set_id: uuid.UUID,
    body: ReportFilterRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.generate_account_summary(
            db, account_set_id=aid, filters=_filters(body), user_id=_user_id(user)
        )
    except ReportError as exc:
        raise _handle_report_error(exc) from exc


@router.post("/{account_set_id}/reports/disclosure-notes")
async def api_disclosure_notes(
    account_set_id: uuid.UUID,
    body: ReportFilterRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await service.generate_disclosure_notes(
            db, account_set_id=aid, filters=_filters(body), user_id=_user_id(user)
        )
    except ReportError as exc:
        raise _handle_report_error(exc) from exc


@router.get("/{account_set_id}/reports/{report_id}/export")
async def api_export_report(
    account_set_id: uuid.UUID,
    report_id: uuid.UUID,
    format: str = Query("pdf", alias="format"),
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    content, media_type, filename = await service.export_report(
        db, account_set_id=aid, report_id=str(report_id), export_format=format
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/{account_set_id}/report-data-sources",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_register_data_source(
    account_set_id: uuid.UUID,
    body: DataSourceCreateRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await data_sources.register_data_source(
            db,
            account_set_id=aid,
            name=body.name,
            connection_mode=body.connection_mode,
            vendor=body.vendor,
            endpoint_url=body.endpoint_url,
            host=body.host,
            port=body.port,
            database_name=body.database_name,
            credentials=body.credentials,
            config=body.config,
        )
    except ReportError as exc:
        raise _handle_report_error(exc) from exc


@router.get("/{account_set_id}/report-data-sources", response_model=list[DataSourceResponse])
async def api_list_data_sources(
    account_set_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await data_sources.list_data_sources(db, account_set_id=aid)


@router.post(
    "/{account_set_id}/report-data-sources/{source_id}/test",
    response_model=ConnectionTestResponse,
)
async def api_test_data_source(
    account_set_id: uuid.UUID,
    source_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    result = await data_sources.test_data_source_connection(
        db, account_set_id=aid, data_source_id=str(source_id)
    )
    return ConnectionTestResponse(**result)


@router.post(
    "/{account_set_id}/report-templates",
    response_model=ReportTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_create_template(
    account_set_id: uuid.UUID,
    body: ReportTemplateCreateRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await templates.create_report_template(
        db,
        account_set_id=aid,
        data_source_id=str(body.data_source_id),
        name=body.name,
        layout=body.layout,
        created_by=_user_id(user),
    )


@router.post(
    "/{account_set_id}/report-templates/{template_id}/publish",
    response_model=ReportTemplateResponse,
)
async def api_publish_template(
    account_set_id: uuid.UUID,
    template_id: uuid.UUID,
    body: ReportTemplatePublishRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await templates.publish_report_template(
        db,
        account_set_id=aid,
        template_id=str(template_id),
        role_ids=body.role_ids,
    )


@router.get("/{account_set_id}/report-templates", response_model=list[ReportTemplateResponse])
async def api_list_templates(
    account_set_id: uuid.UUID,
    role_id: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    return await templates.list_report_templates(db, account_set_id=aid, role_id=role_id)


@router.post("/{account_set_id}/report-templates/{template_id}/run")
async def api_run_template(
    account_set_id: uuid.UUID,
    template_id: uuid.UUID,
    body: ReportFilterRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_REPORTS)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_id_from_user(user, str(account_set_id))
    try:
        return await templates.run_report_template(
            db,
            account_set_id=aid,
            template_id=str(template_id),
            filters=_filters(body),
            user_id=_user_id(user),
        )
    except ReportError as exc:
        raise _handle_report_error(exc) from exc
