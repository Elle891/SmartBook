"""
Tax authority submission client (Req 21.4–21.6).
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

TAX_FILING_URL = os.getenv("TAX_FILING_URL", "http://localhost:8090/tax/filing/submit")
SUBMIT_TIMEOUT_SECONDS = 30.0


def _get_http_client(**kwargs: Any):
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


async def submit_to_tax_authority(
    *,
    account_set_id: str,
    filing_id: str,
    tax_type: str,
    period_code: str,
    report_data: dict[str, Any],
) -> dict[str, Any]:
    """Transmit filing to tax authority; stub mode for tests."""
    if os.getenv("TAX_FILING_URL", "").lower() == "stub":
        return _stub_submit(filing_id, tax_type)

    payload = {
        "account_set_id": account_set_id,
        "filing_id": filing_id,
        "tax_type": tax_type,
        "period_code": period_code,
        "report_data": report_data,
    }
    async with _get_http_client(timeout=SUBMIT_TIMEOUT_SECONDS) as client:
        response = await client.post(TAX_FILING_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        if data.get("success"):
            return {
                "success": True,
                "confirmation_number": str(data.get("confirmation_number", "")),
                "message": str(data.get("message", "Submitted")),
            }
        return {
            "success": False,
            "confirmation_number": None,
            "message": str(data.get("message", "Submission rejected")),
        }


def _stub_submit(filing_id: str, tax_type: str) -> dict[str, Any]:
    if filing_id.startswith("fail-"):
        return {
            "success": False,
            "confirmation_number": None,
            "message": "Tax authority rejected filing: invalid period data",
        }
    return {
        "success": True,
        "confirmation_number": f"CN-{tax_type}-{filing_id[:8].upper()}",
        "message": "Filing accepted",
    }
