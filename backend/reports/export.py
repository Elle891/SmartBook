"""
Report export — PDF and CSV (Req 9.9).
"""

from __future__ import annotations

import csv
import io
from typing import Any

from ledger.export import build_ledger_html, export_to_pdf


def export_report_csv(report_data: dict[str, Any]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["title", report_data.get("title", "")])
    writer.writerow(["standard", report_data.get("standard", "")])
    writer.writerow(["currency", report_data.get("currency", "")])

    if "line_items" in report_data:
        writer.writerow([])
        writer.writerow(["label", "amount", "amount_formatted"])
        for item in report_data["line_items"]:
            writer.writerow(
                [
                    item.get("label") or item.get("section", ""),
                    item.get("amount", ""),
                    item.get("amount_formatted", ""),
                ]
            )
    elif "rows" in report_data:
        writer.writerow([])
        if report_data["rows"]:
            headers = list(report_data["rows"][0].keys())
            writer.writerow(headers)
            for row in report_data["rows"]:
                writer.writerow([row.get(h, "") for h in headers])
    elif "sections" in report_data and isinstance(report_data["sections"], list):
        writer.writerow([])
        writer.writerow(["heading", "content"])
        for sec in report_data["sections"]:
            writer.writerow([sec.get("heading", ""), sec.get("content", "")])

    return buffer.getvalue().encode("utf-8-sig")


def export_report_pdf(report_data: dict[str, Any]) -> bytes:
    rows = []
    columns: list[tuple[str, str]] = []

    if "line_items" in report_data:
        columns = [("label", "Line Item"), ("amount_formatted", "Amount")]
        for item in report_data["line_items"]:
            rows.append(
                {
                    "label": item.get("label") or item.get("section", ""),
                    "amount_formatted": item.get("amount_formatted", item.get("amount", "")),
                }
            )
    elif "rows" in report_data:
        columns = [
            ("account_code", "Account"),
            ("account_name", "Name"),
            ("total_debits_formatted", "Debits"),
            ("total_credits_formatted", "Credits"),
        ]
        rows = report_data["rows"]
    else:
        columns = [("heading", "Section"), ("content", "Content")]
        rows = report_data.get("sections", [])

    html = build_ledger_html(
        report_data.get("title", "Report"),
        rows,
        columns=columns,
    )
    return export_to_pdf(html)
