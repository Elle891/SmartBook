"""ISO 20022 pain.001 generation and UETR."""

from __future__ import annotations

import uuid
from typing import Any


MANDATORY_FIELDS = (
    "debtor_account",
    "creditor_name",
    "creditor_account",
    "payment_currency",
    "instructed_amount",
    "value_date",
)


def generate_uetr() -> str:
    return str(uuid.uuid4())


def validate_required_fields(payment: Any) -> None:
    missing = []
    if not getattr(payment, "recipient_account", None):
        missing.append("creditor_account")
    if not getattr(payment, "recipient_name", None):
        missing.append("creditor_name")
    if not getattr(payment, "currency", None):
        missing.append("payment_currency")
    if float(getattr(payment, "amount", 0)) <= 0:
        missing.append("instructed_amount")
    if not getattr(payment, "scheduled_date", None):
        missing.append("value_date")
    if missing:
        from payment.stages import WorkflowError

        raise WorkflowError(
            "Required ISO 20022 fields are missing.",
            details={"missing_fields": missing},
        )


def build_pain001(payment: Any, *, debtor_account: str = "") -> str:
    """Build a minimal pain.001 XML payload."""
    return (
        '<?xml version="1.0"?>'
        "<Document>"
        "<CstmrCdtTrfInitn>"
        f"<PmtInfId>{payment.id}</PmtInfId>"
        f"<DbtrAcct>{debtor_account or payment.connection_id}</DbtrAcct>"
        f"<CdtrNm>{payment.recipient_name}</CdtrNm>"
        f"<CdtrAcct>{payment.recipient_account}</CdtrAcct>"
        f"<InstdAmt Ccy='{payment.currency}'>{payment.amount}</InstdAmt>"
        f"<ReqdExctnDt>{payment.scheduled_date}</ReqdExctnDt>"
        "</CstmrCdtTrfInitn>"
        "</Document>"
    )
