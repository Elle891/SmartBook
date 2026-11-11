"""JSON helpers for MCP tool responses."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _default(obj: Any) -> Any:
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        data = {
            k: v
            for k, v in vars(obj).items()
            if not k.startswith("_") and not callable(v)
        }
        if data:
            return data
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def dumps_json(payload: Any) -> str:
    """Serialize payloads for MCP tool results (always a JSON string)."""
    return json.dumps(payload, default=_default, ensure_ascii=False, indent=2)


def voucher_summary(voucher: Any) -> dict[str, Any]:
    return {
        "id": str(voucher.id),
        "account_set_id": str(voucher.account_set_id),
        "period_code": voucher.period_code,
        "voucher_number": voucher.voucher_number,
        "type": voucher.type,
        "date": voucher.date.isoformat() if getattr(voucher, "date", None) else None,
        "status": voucher.status,
        "created_by": str(voucher.created_by) if voucher.created_by else None,
        "reviewed_by": str(voucher.reviewed_by) if getattr(voucher, "reviewed_by", None) else None,
        "rejection_reason": getattr(voucher, "rejection_reason", None),
    }


def voucher_detail(voucher: Any) -> dict[str, Any]:
    summary = voucher_summary(voucher)
    entries = []
    for entry in getattr(voucher, "entries", None) or []:
        entries.append(
            {
                "id": str(getattr(entry, "id", "")),
                "account_code": getattr(entry, "account_code", None),
                "debit_amount": float(entry.debit_amount)
                if getattr(entry, "debit_amount", None) is not None
                else 0.0,
                "credit_amount": float(entry.credit_amount)
                if getattr(entry, "credit_amount", None) is not None
                else 0.0,
                "description": getattr(entry, "description", None) or "",
                "aux_dimension_values": getattr(entry, "aux_dimension_values", None) or {},
                "sequence": getattr(entry, "sequence", 0),
            }
        )
    summary["entries"] = entries
    return summary


def account_set_summary(account_set: Any) -> dict[str, Any]:
    return {
        "id": str(account_set.id),
        "name": account_set.name,
        "journal_set_no": account_set.journal_set_no,
        "standard": account_set.standard,
        "base_currency": account_set.base_currency,
        "start_period": account_set.start_period,
        "datasource_type": account_set.datasource_type,
        "status": account_set.status,
    }
