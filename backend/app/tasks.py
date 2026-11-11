"""
Celery tasks for svc-accounting background processing.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import InstrumentedTask, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    base=InstrumentedTask,
    name="ledger.process_voucher_events",
    bind=True,
)
def process_voucher_events(self, batch_size: int = 10) -> dict[str, int]:
    """Consume voucher-approved Redis Stream events and materialize ledger rows."""
    from ledger.consumer import process_pending_voucher_events

    processed = asyncio.run(process_pending_voucher_events(batch_size=batch_size))
    logger.info("Ledger consumer processed %s events", processed)
    return {"processed": processed}


@celery_app.task(
    base=InstrumentedTask,
    name="payroll.generate_payslips",
    bind=True,
)
def generate_payslips_task(self, account_set_id: str, period_code: str) -> dict[str, Any]:
    """Async Celery task to generate payslips (Req 17.6)."""
    from payroll.runner import with_tenant_session
    from payroll import service

    async def _run(db: AsyncSession) -> dict[str, Any]:
        payslips = await service.generate_payslips(
            db, account_set_id=account_set_id, period_code=period_code
        )
        return {"count": len(payslips), "payslips": payslips}

    result = asyncio.run(with_tenant_session(account_set_id, _run))
    return result


@celery_app.task(
    base=InstrumentedTask,
    name="payroll.distribute_payslips",
    bind=True,
)
def distribute_payslips_task(
    self,
    account_set_id: str,
    period_code: str,
    channel: str,
) -> dict[str, Any]:
    """Async Celery task to distribute payslips (Req 17.7)."""
    from payroll.runner import with_tenant_session
    from payroll import service

    async def _run(db: AsyncSession) -> dict[str, Any]:
        return await service.distribute_payslips(
            db,
            account_set_id=account_set_id,
            period_code=period_code,
            channel=channel,
        )

    return asyncio.run(with_tenant_session(account_set_id, _run))


@celery_app.task(
    base=InstrumentedTask,
    name="invoice_scanner.process_ocr",
    bind=True,
)
def process_invoice_ocr_task(self, account_set_id: str, job_id: str) -> dict[str, str]:
    """Async Celery task for invoice OCR + verification (Req 20.2, 20.3)."""
    from invoice_scanner import service
    from payroll.runner import with_tenant_session

    async def _run(db: AsyncSession) -> dict[str, str]:
        job = await service.run_ocr_pipeline(
            db, account_set_id=account_set_id, job_id=job_id
        )
        return {"job_id": str(job.id), "status": job.status}

    return asyncio.run(with_tenant_session(account_set_id, _run))


@celery_app.task(
    base=InstrumentedTask,
    name="bank.sync_connection",
    bind=True,
)
def sync_bank_connection_task(
    self, account_set_id: str, connection_id: str
) -> dict[str, Any]:
    """On-demand or scheduled bank transaction sync (Req 3.1)."""
    from bank import service
    from payroll.runner import with_tenant_session

    async def _run(db: AsyncSession) -> dict[str, Any]:
        return await service.sync_transactions(
            db,
            account_set_id=account_set_id,
            connection_id=connection_id,
        )

    return asyncio.run(with_tenant_session(account_set_id, _run))


@celery_app.task(
    base=InstrumentedTask,
    name="bank.sync_scheduled",
    bind=True,
)
def sync_bank_scheduled_task(self) -> dict[str, Any]:
    """Daily bank sync for configured account sets (Celery beat)."""
    import os

    from bank import service
    from payroll.runner import with_tenant_session

    account_set_ids = [
        aid.strip()
        for aid in os.getenv("BANK_SYNC_ACCOUNT_SET_IDS", "").split(",")
        if aid.strip()
    ]
    results: list[dict[str, Any]] = []
    for account_set_id in account_set_ids:

        async def _run(db: AsyncSession, aid: str = account_set_id) -> dict[str, Any]:
            return await service.sync_all_connections(db, account_set_id=aid)

        results.append(asyncio.run(with_tenant_session(account_set_id, _run)))
    return {"synced_account_sets": len(results), "results": results}


@celery_app.task(
    base=InstrumentedTask,
    name="payment.confirm_scheduled",
    bind=True,
)
def confirm_scheduled_payments_task(self) -> dict[str, Any]:
    """Every minute: confirm Authorised payments with scheduled_date <= today."""
    import os

    from payment import workflow
    from payroll.runner import with_tenant_session

    account_set_ids = [
        aid.strip()
        for aid in os.getenv("PAYMENT_SYNC_ACCOUNT_SET_IDS", "").split(",")
        if aid.strip()
    ]
    results: list[dict[str, Any]] = []
    for account_set_id in account_set_ids:

        async def _run(db: AsyncSession, aid: str = account_set_id) -> dict[str, Any]:
            return await workflow.confirm_scheduled_payments(db, account_set_id=aid)

        results.append(asyncio.run(with_tenant_session(account_set_id, _run)))
    return {"account_sets": len(results), "results": results}


@celery_app.task(
    base=InstrumentedTask,
    name="ml.train_forecast_model",
    bind=True,
)
def train_forecast_model_task(self, account_set_id: str) -> dict[str, Any]:
    """Train or retrain cash flow forecast model (Task 28)."""
    from ml.training import train_model
    from payroll.runner import with_tenant_session

    async def _run(db: AsyncSession) -> dict[str, Any]:
        return await train_model(db, account_set_id=account_set_id)

    return asyncio.run(with_tenant_session(account_set_id, _run))
