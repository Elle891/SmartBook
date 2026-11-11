"""
Report template lifecycle (Req 9.12).
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.report_engine import (
    TEMPLATE_DRAFT,
    TEMPLATE_PUBLISHED,
    ReportDataSource,
    ReportTemplate,
)
from reports.filters import ReportFilter
from reports import service as report_service


async def create_report_template(
    db: AsyncSession,
    *,
    account_set_id: str,
    data_source_id: str,
    name: str,
    layout: dict[str, Any],
    created_by: str,
) -> ReportTemplate:
    ds_result = await db.execute(
        select(ReportDataSource).where(
            ReportDataSource.id == data_source_id,
            ReportDataSource.account_set_id == account_set_id,
        )
    )
    if ds_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found.")

    template = ReportTemplate(
        account_set_id=account_set_id,
        data_source_id=data_source_id,
        name=name,
        layout=layout,
        status=TEMPLATE_DRAFT,
        created_by=created_by,
    )
    db.add(template)
    await db.flush()
    return template


async def publish_report_template(
    db: AsyncSession,
    *,
    account_set_id: str,
    template_id: str,
    role_ids: list[str],
) -> ReportTemplate:
    template = await _get_template(db, account_set_id, template_id)
    template.status = TEMPLATE_PUBLISHED
    template.published_role_ids = role_ids
    await db.flush()
    return template


async def list_report_templates(
    db: AsyncSession,
    *,
    account_set_id: str,
    role_id: str | None = None,
) -> list[ReportTemplate]:
    result = await db.execute(
        select(ReportTemplate)
        .where(ReportTemplate.account_set_id == account_set_id)
        .order_by(ReportTemplate.name)
    )
    templates = list(result.scalars().all())
    if role_id is None:
        return templates
    return [
        t
        for t in templates
        if t.status == TEMPLATE_PUBLISHED
        and t.published_role_ids
        and role_id in [str(r) for r in t.published_role_ids]
    ]


async def run_report_template(
    db: AsyncSession,
    *,
    account_set_id: str,
    template_id: str,
    filters: ReportFilter,
    user_id: str,
) -> dict[str, Any]:
    template = await _get_template(db, account_set_id, template_id)
    report_type = template.layout.get("report_type", "AccountSummary")
    if report_type == "BalanceSheet":
        return await report_service.generate_balance_sheet(
            db, account_set_id=account_set_id, filters=filters, user_id=user_id
        )
    if report_type == "IncomeStatement":
        return await report_service.generate_income_statement(
            db, account_set_id=account_set_id, filters=filters, user_id=user_id
        )
    if report_type == "CashFlow":
        return await report_service.generate_cash_flow_statement(
            db, account_set_id=account_set_id, filters=filters, user_id=user_id
        )
    return await report_service.generate_account_summary(
        db, account_set_id=account_set_id, filters=filters, user_id=user_id
    )


async def _get_template(
    db: AsyncSession,
    account_set_id: str,
    template_id: str,
) -> ReportTemplate:
    result = await db.execute(
        select(ReportTemplate).where(
            ReportTemplate.id == template_id,
            ReportTemplate.account_set_id == account_set_id,
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report template not found.")
    return template
