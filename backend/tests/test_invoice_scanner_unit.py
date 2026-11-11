"""
Unit tests for Invoice Scanner — OCR, verification, voucher with attachment.

_Requirements: 20.1–20.7 (Task 17.1)_
"""

from __future__ import annotations

import os
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from invoice_scanner import clients, storage
from invoice_scanner.voucher_builder import build_invoice_voucher_entries
from invoice_scanner.service import _validate_invoice_file


@pytest.fixture(autouse=True)
def _invoice_test_env(monkeypatch):
    monkeypatch.setenv("INVOICE_STORAGE_BACKEND", "memory")
    monkeypatch.setenv("OCR_SERVICE_URL", "stub")
    monkeypatch.setenv("TAX_VERIFY_URL", "stub")
    storage.clear_memory_store()
    yield
    storage.clear_memory_store()


class TestFileValidation:
    def test_accepts_jpeg(self):
        assert _validate_invoice_file("invoice.jpg", "image/jpeg") == "jpg"

    def test_accepts_pdf(self):
        assert _validate_invoice_file("invoice.pdf", "application/pdf") == "pdf"

    def test_rejects_unsupported_format(self):
        with pytest.raises(HTTPException) as exc:
            _validate_invoice_file("invoice.png", "image/png")
        assert exc.value.status_code == 422


class TestOcrExtraction:
    @pytest.mark.asyncio
    async def test_extract_invoice_fields_stub(self):
        data = await clients.extract_invoice_fields(
            image_bytes=b"invoice image content",
            content_type="image/jpeg",
            filename="invoice.jpg",
        )
        assert data["invoice_number"] == "INV-2025-001"
        assert data["amount_excl_tax"] == 1000.0
        assert data["tax_amount"] == 130.0
        assert "Office supplies" in data["item_descriptions"][0]


class TestTaxVerification:
    @pytest.mark.asyncio
    async def test_verification_success(self):
        result = await clients.verify_with_tax_authority(
            invoice_number="INV-2025-001",
            amount_excl_tax=1000.0,
            tax_amount=130.0,
        )
        assert result["verified"] is True
        assert result["verification_status"] == "Verified"

    @pytest.mark.asyncio
    async def test_verification_failure_reason(self):
        result = await clients.verify_with_tax_authority(
            invoice_number="BAD-001",
            amount_excl_tax=1000.0,
            tax_amount=130.0,
        )
        assert result["verified"] is False
        assert "not found" in result["reason"].lower()


class TestVoucherBuilder:
    def test_entries_balance(self):
        entries = build_invoice_voucher_entries(
            amount_excl_tax=1000.0,
            tax_amount=130.0,
            description="Office supplies",
        )
        debits = sum(e["debit_amount"] for e in entries)
        credits = sum(e["credit_amount"] for e in entries)
        assert debits == credits == 1130.0
        accounts = {e["account_code"] for e in entries}
        assert accounts == {"6602", "2221", "2202"}


class TestSubmitAndRoundTrip:
    @pytest.mark.asyncio
    async def test_submit_stores_image_for_round_trip(self):
        from invoice_scanner import service as inv_svc

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        job = await inv_svc.submit_invoice(
            db,
            account_set_id="as-1",
            filename="invoice.jpg",
            content=b"test invoice bytes",
            content_type="image/jpeg",
            user_id="u1",
            enqueue_ocr=False,
        )

        downloaded = storage.download_bytes(job.image_key)
        assert downloaded == b"test invoice bytes"


class TestGenerateVoucher:
    @pytest.mark.asyncio
    async def test_rejects_unverified_without_override(self):
        from invoice_scanner import service as inv_svc

        job = MagicMock()
        job.voucher_id = None
        job.extracted_data = {
            "invoice_number": "BAD-001",
            "invoice_date": "2025-01-15",
            "amount_excl_tax": 1000.0,
            "tax_amount": 130.0,
            "item_descriptions": ["Supplies"],
        }
        job.verification_result = {
            "verified": False,
            "reason": "Not found",
            "verification_status": "Failed",
        }
        job.image_key = "as-1/invoices/job-1.jpg"

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = job
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc:
            await inv_svc.generate_voucher(
                db,
                account_set_id="as-1",
                job_id="job-1",
                user_id="u1",
            )
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_voucher_with_attachment(self):
        from invoice_scanner import service as inv_svc

        image_key = storage.upload_bytes(
            key="as-1/invoices/job-2.jpg",
            content=b"original invoice",
            content_type="image/jpeg",
        )

        job = MagicMock()
        job.id = "job-2"
        job.voucher_id = None
        job.image_key = image_key
        job.extracted_data = {
            "invoice_number": "INV-2025-001",
            "invoice_date": "2025-01-15",
            "seller_name": "Seller",
            "buyer_name": "Buyer",
            "item_descriptions": ["Supplies"],
            "amount_excl_tax": 1000.0,
            "tax_amount": 130.0,
        }
        job.verification_result = {
            "verified": True,
            "reason": "",
            "verification_status": "Verified",
        }

        voucher = MagicMock()
        voucher.id = "v-1"

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = job
        db.execute = AsyncMock(return_value=result_mock)
        db.flush = AsyncMock()

        create_mock = AsyncMock(return_value=voucher)
        with (
            patch.object(inv_svc, "assert_period_open", AsyncMock()),
            patch.object(inv_svc, "create_voucher", create_mock),
        ):
            result = await inv_svc.generate_voucher(
                db,
                account_set_id="as-1",
                job_id="job-2",
                user_id="u1",
            )

        assert result["voucher_id"] == "v-1"
        create_mock.assert_awaited_once()
        call_kwargs = create_mock.await_args.kwargs
        assert call_kwargs["attachments"][0]["file_key"] == image_key
        assert job.voucher_id == voucher.id


class TestGetAttachment:
    @pytest.mark.asyncio
    async def test_returns_original_bytes(self):
        from invoice_scanner import service as inv_svc

        key = storage.upload_bytes(
            key="as-1/invoices/v1.jpg",
            content=b"round-trip-bytes",
            content_type="image/jpeg",
        )
        att = MagicMock()
        att.file_key = key
        att.filename = "v1.jpg"

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [att]
        db.execute = AsyncMock(return_value=result_mock)

        payload = await inv_svc.get_attachment(
            db, account_set_id="as-1", voucher_id="v-1"
        )
        assert payload["content"] == b"round-trip-bytes"
        assert payload["content_type"] == "image/jpeg"
