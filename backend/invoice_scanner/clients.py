"""
OCR extraction and tax authority verification clients.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

VERIFY_TIMEOUT_SECONDS = 10.0

OCR_SERVICE_URL = os.getenv("OCR_SERVICE_URL", "http://localhost:8090/ocr/extract")
TAX_VERIFY_URL = os.getenv("TAX_VERIFY_URL", "http://localhost:8090/tax/verify")

REQUIRED_OCR_FIELDS = (
    "invoice_number",
    "invoice_date",
    "seller_name",
    "buyer_name",
    "item_descriptions",
    "amount_excl_tax",
    "tax_amount",
)


def _get_http_client(**kwargs: Any):
    """Load backend HTTP client without shadowing stdlib `platform` in tests."""
    backend = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "svc_accounting_http_client",
        backend / "platform" / "http_client.py",
    )
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load platform http_client module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_http_client(**kwargs)


def normalize_extracted_data(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize OCR response into canonical invoice fields (Req 20.2)."""
    items = raw.get("item_descriptions") or raw.get("items") or []
    if isinstance(items, str):
        items = [items]
    return {
        "invoice_number": str(raw.get("invoice_number", "")),
        "invoice_date": str(raw.get("invoice_date", "")),
        "seller_name": str(raw.get("seller_name", "")),
        "buyer_name": str(raw.get("buyer_name", "")),
        "item_descriptions": [str(i) for i in items],
        "amount_excl_tax": float(raw.get("amount_excl_tax", 0) or 0),
        "tax_amount": float(raw.get("tax_amount", 0) or 0),
    }


async def extract_invoice_fields(
    *,
    image_bytes: bytes,
    content_type: str,
    filename: str,
) -> dict[str, Any]:
    """Call OCR service via httpx; falls back to stub parser in test mode."""
    if os.getenv("OCR_SERVICE_URL", "").lower() == "stub":
        return _stub_extract(filename, image_bytes)

    async with _get_http_client(timeout=30.0) as client:
        response = await client.post(
            OCR_SERVICE_URL,
            files={"file": (filename, image_bytes, content_type)},
        )
        response.raise_for_status()
        return normalize_extracted_data(response.json())


def _stub_extract(filename: str, image_bytes: bytes) -> dict[str, Any]:
    """Deterministic stub for unit tests when OCR_SERVICE_URL=stub."""
    text = image_bytes.decode("utf-8", errors="ignore")
    return normalize_extracted_data(
        {
            "invoice_number": "INV-2025-001",
            "invoice_date": "2025-01-15",
            "seller_name": "Acme Supplier Ltd",
            "buyer_name": "SmartBook Enterprise",
            "item_descriptions": ["Office supplies"],
            "amount_excl_tax": 1000.0,
            "tax_amount": 130.0,
            "raw_text": text[:64],
            "filename": filename,
        }
    )


async def verify_with_tax_authority(
    *,
    invoice_number: str,
    amount_excl_tax: float,
    tax_amount: float,
) -> dict[str, Any]:
    """Verify invoice against tax authority API within 10 seconds (Req 20.3)."""
    total = amount_excl_tax + tax_amount
    if os.getenv("TAX_VERIFY_URL", "").lower() == "stub":
        return _stub_verify(invoice_number, total)

    payload = {
        "invoice_number": invoice_number,
        "amount_excl_tax": amount_excl_tax,
        "tax_amount": tax_amount,
        "total_amount": total,
    }
    async with _get_http_client(timeout=VERIFY_TIMEOUT_SECONDS) as client:
        response = await client.post(TAX_VERIFY_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        return {
            "verified": bool(data.get("verified", False)),
            "reason": str(data.get("reason", "")),
            "verification_status": "Verified" if data.get("verified") else "Failed",
        }


def _stub_verify(invoice_number: str, total: float) -> dict[str, Any]:
    if invoice_number.startswith("BAD-"):
        return {
            "verified": False,
            "reason": "Invoice not found in tax authority database",
            "verification_status": "Failed",
        }
    return {
        "verified": True,
        "reason": "",
        "verification_status": "Verified",
    }
