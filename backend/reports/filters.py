"""
Report filter parsing and validation (Req 9.11).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from reports.errors import ReportValidationError


@dataclass
class ReportFilter:
    period_code: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    report_currency: str | None = None
    entity_id: str | None = None
    entity_group_id: str | None = None
    account_code: str | None = None
    cash_flow_method: str | None = None  # Direct | Indirect

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReportFilter:
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        return cls(
            period_code=data.get("period_code"),
            date_from=date.fromisoformat(date_from[:10]) if date_from else None,
            date_to=date.fromisoformat(date_to[:10]) if date_to else None,
            report_currency=data.get("report_currency"),
            entity_id=data.get("entity_id"),
            entity_group_id=data.get("entity_group_id"),
            account_code=data.get("account_code"),
            cash_flow_method=data.get("cash_flow_method"),
        )

    def validate(self) -> None:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ReportValidationError("date_from must be on or before date_to.")
        if self.entity_id and self.entity_group_id:
            raise ReportValidationError(
                "Specify either entity_id or entity_group_id, not both."
            )
        if not self.period_code and not (self.date_from and self.date_to):
            raise ReportValidationError(
                "Provide period_code or both date_from and date_to."
            )

    def effective_period_code(self) -> str:
        if self.period_code:
            return self.period_code
        assert self.date_from is not None
        return f"{self.date_from.year}{self.date_from.month:02d}"
