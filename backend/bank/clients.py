"""
Bank API client — live HTTP or stub mode for tests (Req 2.1, 2.4).
"""

from __future__ import annotations

import importlib.util
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

BANK_API_URL = os.getenv("BANK_API_URL", "http://localhost:8091/bank")
REQUEST_TIMEOUT_SECONDS = 5.0


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


def _stub_mode() -> bool:
    return os.getenv("BANK_API_URL", "").lower() == "stub"


async def verify_connection(
    *,
    bank_code: str,
    account_number: str,
    credentials: dict[str, Any],
) -> dict[str, Any]:
    if _stub_mode():
        if credentials.get("force_fail"):
            return {"connected": False, "message": "Invalid bank credentials (stub)."}
        return {
            "connected": True,
            "message": f"Connected to {bank_code} account {account_number[-4:].rjust(len(account_number), '*')}",
        }

    payload = {
        "bank_code": bank_code,
        "account_number": account_number,
        "credentials": credentials,
    }
    async with _get_http_client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(f"{BANK_API_URL}/verify", json=payload)
        response.raise_for_status()
        return response.json()


async def fetch_balance(
    *,
    bank_code: str,
    account_number: str,
    credentials: dict[str, Any],
    as_of: date | None = None,
) -> dict[str, Any]:
    if _stub_mode():
        if credentials.get("force_balance_fail"):
            raise TimeoutError("Bank balance API timed out (stub).")
        return {
            "currency": "CNY",
            "current_balance": 125000.50,
            "opening_balance": 120000.00,
            "closing_balance": 125000.50,
            "as_of": (as_of or date.today()).isoformat(),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }

    payload = {
        "bank_code": bank_code,
        "account_number": account_number,
        "credentials": credentials,
        "as_of": as_of.isoformat() if as_of else None,
    }
    async with _get_http_client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(f"{BANK_API_URL}/balance", json=payload)
        response.raise_for_status()
        return response.json()


async def fetch_transactions(
    *,
    bank_code: str,
    account_number: str,
    credentials: dict[str, Any],
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    if _stub_mode():
        if credentials.get("force_sync_fail"):
            raise ConnectionError("Bank API unavailable (stub).")
        today = date.today()
        return [
            {
                "date": today.isoformat(),
                "amount": 1500.0,
                "direction": "Inflow",
                "description": "Customer payment",
                "reference_number": "STUB-IN-001",
            },
            {
                "date": today.isoformat(),
                "amount": 800.0,
                "direction": "Outflow",
                "description": "Supplier payment",
                "reference_number": "STUB-OUT-001",
            },
        ]

    payload = {
        "bank_code": bank_code,
        "account_number": account_number,
        "credentials": credentials,
        "since": since.isoformat() if since else None,
    }
    async with _get_http_client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(f"{BANK_API_URL}/transactions", json=payload)
        response.raise_for_status()
        data = response.json()
        return list(data.get("transactions", []))
