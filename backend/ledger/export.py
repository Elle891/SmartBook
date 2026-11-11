"""
Ledger export — PDF (WeasyPrint) and Excel (openpyxl).
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any


def build_ledger_html(
    title: str,
    rows: list[dict[str, Any]],
    *,
    columns: list[tuple[str, str]],
) -> str:
    """Build simple HTML table for PDF export."""
    headers = "".join(f"<th>{label}</th>" for _, label in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{row.get(key, '')}</td>" for key, _ in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    tbody = "\n".join(body_rows)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
  body {{ font-family: sans-serif; font-size: 12px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; }}
  th {{ background: #f0f0f0; }}
  h1 {{ font-size: 16px; }}
</style></head>
<body>
<h1>{title}</h1>
<p>Generated: {date.today().isoformat()}</p>
<table><thead><tr>{headers}</tr></thead><tbody>{tbody}</tbody></table>
</body></html>"""


def export_to_pdf(html: str) -> bytes:
    try:
        from weasyprint import HTML

        return HTML(string=html).write_pdf()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "PDF export requires WeasyPrint and its system dependencies."
        ) from exc


def export_to_excel(
    sheet_name: str,
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str]],
) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]
    ws.append([label for _, label in columns])
    for row in rows:
        ws.append([row.get(key, "") for key, _ in columns])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


GENERAL_LEDGER_COLUMNS = [
    ("entry_date", "Date"),
    ("voucher_number", "Voucher #"),
    ("account_code", "Account"),
    ("description", "Description"),
    ("debit_amount", "Debit"),
    ("credit_amount", "Credit"),
    ("running_balance", "Balance"),
]

ACCOUNT_SUMMARY_COLUMNS = [
    ("account_code", "Account Code"),
    ("account_name", "Account Name"),
    ("opening_balance", "Opening"),
    ("total_debits", "Debits"),
    ("total_credits", "Credits"),
    ("closing_balance", "Closing"),
]
