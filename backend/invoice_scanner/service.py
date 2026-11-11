"""
Invoice Scanner service — submit, OCR, verify, voucher generation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_scanner import clients, storage
from invoice_scanner.voucher_builder import build_invoice_voucher_entries, merge_confirmed_data
from models.reports import InvoiceScanJob
from models.voucher import VoucherAttachment
from period_end.periods import assert_period_open
from voucher.service import create_voucher

logger = logging.getLogger(__name__)

STATUS_PENDING = "Pending"
STATUS_PROCESSING = "Processing"
STATUS_COMPLETED = "Completed"
STATUS_FAILED = "Failed"

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "application/pdf": "pdf",
}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".pdf"}


def _validate_invoice_file(filename: str, content_type: str | None) -> str:
    """Validate JPEG/PDF upload (Req 20.1)."""
    lower = filename.lower()
    ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invoice must be JPEG or PDF format.",
        )
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported content type: {content_type}",
        )
    return ALLOWED_CONTENT_TYPES.get(content_type or "", ext.lstrip("."))


def _period_code_from_date(invoice_date: date) -> str:
    return f"{invoice_date.year}{invoice_date.month:02d}"


def _parse_invoice_date(value: str) -> date:
    return date.fromisoformat(value[:10])


async def submit_invoice(
    db: AsyncSession,
    *,
    account_set_id: str,
    filename: str,
    content: bytes,
    content_type: str | None,
    user_id: str,
    enqueue_ocr: bool = True,
) -> InvoiceScanJob:
    """Store image in S3 and create scan job (Req 20.1)."""
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )
    _validate_invoice_file(filename, content_type)

    job_id = str(uuid.uuid4())
    image_key = storage.build_image_key(account_set_id, job_id, filename)
    mime = content_type or "application/octet-stream"
    storage.upload_bytes(key=image_key, content=content, content_type=mime)

    job = InvoiceScanJob(
        id=job_id,
        account_set_id=account_set_id,
        image_key=image_key,
        status=STATUS_PENDING,
    )
    db.add(job)
    await db.flush()

    if enqueue_ocr:
        from app.tasks import process_invoice_ocr_task

        process_invoice_ocr_task.delay(account_set_id, job_id)

    return job


async def extract_invoice_data(
    db: AsyncSession,
    *,
    account_set_id: str,
    job_id: str,
) -> dict[str, Any]:
    """Run OCR on stored invoice image (Req 20.2)."""
    job = await _get_job(db, account_set_id, job_id)
    image_bytes = storage.download_bytes(job.image_key)
    filename = job.image_key.rsplit("/", 1)[-1]
    content_type = "application/pdf" if filename.endswith(".pdf") else "image/jpeg"

    job.status = STATUS_PROCESSING
    await db.flush()

    try:
        extracted = await clients.extract_invoice_fields(
            image_bytes=image_bytes,
            content_type=content_type,
            filename=filename,
        )
        job.extracted_data = extracted
        job.status = STATUS_COMPLETED
        await db.flush()
        return extracted
    except Exception as exc:
        job.status = STATUS_FAILED
        job.extracted_data = {"error": str(exc)}
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OCR extraction failed: {exc}",
        ) from exc


async def verify_invoice(
    db: AsyncSession,
    *,
    account_set_id: str,
    job_id: str,
    confirmed_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify invoice with tax authority (Req 20.3, 20.4)."""
    job = await _get_job(db, account_set_id, job_id)
    if not job.extracted_data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invoice data not extracted yet.",
        )

    data = merge_confirmed_data(job.extracted_data, confirmed_data)
    result = await clients.verify_with_tax_authority(
        invoice_number=data["invoice_number"],
        amount_excl_tax=float(data["amount_excl_tax"]),
        tax_amount=float(data["tax_amount"]),
    )
    job.verification_result = result
    if confirmed_data:
        job.extracted_data = data
    await db.flush()
    return result


async def run_ocr_pipeline(
    db: AsyncSession,
    *,
    account_set_id: str,
    job_id: str,
) -> InvoiceScanJob:
    """Celery pipeline: OCR then tax verification."""
    await extract_invoice_data(db, account_set_id=account_set_id, job_id=job_id)
    try:
        await verify_invoice(db, account_set_id=account_set_id, job_id=job_id)
    except HTTPException:
        logger.warning("Verification skipped after OCR for job %s", job_id)
    result = await db.execute(
        select(InvoiceScanJob).where(InvoiceScanJob.id == job_id)
    )
    return result.scalar_one()


async def generate_voucher(
    db: AsyncSession,
    *,
    account_set_id: str,
    job_id: str,
    user_id: str,
    confirmed_data: dict[str, Any] | None = None,
    period_code: str | None = None,
    expense_account: str | None = None,
    tax_account: str | None = None,
    payable_account: str | None = None,
    allow_unverified: bool = False,
) -> dict[str, Any]:
    """Generate voucher with expense/tax/payable entries and image attachment (Req 20.5, 20.6)."""
    job = await _get_job(db, account_set_id, job_id)
    if job.voucher_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Voucher already generated for this scan job.",
        )
    if not job.extracted_data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invoice data not extracted yet.",
        )

    data = merge_confirmed_data(job.extracted_data, confirmed_data)
    verification = job.verification_result or {}
    if not verification.get("verified") and not allow_unverified:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Invoice verification failed. Correct data and set allow_unverified=true to proceed.",
                "reason": verification.get("reason", "Not verified"),
            },
        )

    invoice_date = _parse_invoice_date(data["invoice_date"])
    pcode = period_code or _period_code_from_date(invoice_date)
    await assert_period_open(db, account_set_id, pcode)

    description = ", ".join(data.get("item_descriptions") or []) or data.get("seller_name", "Invoice")
    entries = build_invoice_voucher_entries(
        amount_excl_tax=float(data["amount_excl_tax"]),
        tax_amount=float(data["tax_amount"]),
        description=description,
        expense_account=expense_account or "6602",
        tax_account=tax_account or "2221",
        payable_account=payable_account or "2202",
    )

    filename = job.image_key.rsplit("/", 1)[-1]
    voucher = await create_voucher(
        db,
        account_set_id=account_set_id,
        period_code=pcode,
        voucher_type="Payment",
        voucher_date=invoice_date,
        entries=entries,
        attachments=[{"file_key": job.image_key, "filename": filename}],
        created_by_user_id=user_id,
    )

    job.extracted_data = data
    job.voucher_id = voucher.id
    await db.flush()

    return {
        "job_id": str(job.id),
        "voucher_id": str(voucher.id),
        "verification_status": verification.get("verification_status", "Unknown"),
    }


async def get_attachment(
    db: AsyncSession,
    *,
    account_set_id: str,
    voucher_id: str,
) -> dict[str, Any]:
    """Return original invoice image for voucher (Req 20.7 round-trip)."""
    result = await db.execute(
        select(VoucherAttachment).where(VoucherAttachment.voucher_id == voucher_id)
    )
    attachments = list(result.scalars().all())
    if not attachments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No attachment found for voucher.",
        )

    att = attachments[0]
    content = storage.download_bytes(att.file_key)
    content_type = "application/pdf" if att.filename.lower().endswith(".pdf") else "image/jpeg"
    return {
        "file_key": att.file_key,
        "filename": att.filename,
        "content_type": content_type,
        "content": content,
    }


async def get_scan_job(
    db: AsyncSession,
    *,
    account_set_id: str,
    job_id: str,
) -> InvoiceScanJob:
    return await _get_job(db, account_set_id, job_id)


async def _get_job(
    db: AsyncSession,
    account_set_id: str,
    job_id: str,
) -> InvoiceScanJob:
    result = await db.execute(
        select(InvoiceScanJob).where(
            InvoiceScanJob.id == job_id,
            InvoiceScanJob.account_set_id == account_set_id,
        )
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice scan job not found.")
    return job
