"""Forecast export helpers (PDF/CSV)."""

from __future__ import annotations

import csv
import io
from typing import Any

from ledger.export import export_to_pdf


def export_forecast_csv(payload: dict[str, Any]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "period_code",
            "predicted_inflow",
            "predicted_outflow",
            "predicted_net_cash_flow",
            "confidence_lower",
            "confidence_upper",
        ]
    )
    for period in payload.get("periods", []):
        writer.writerow(
            [
                period["period_code"],
                period["predicted_inflow"],
                period["predicted_outflow"],
                period["predicted_net_cash_flow"],
                period["confidence_lower"],
                period["confidence_upper"],
            ]
        )
    metrics = payload.get("metrics", {})
    writer.writerow([])
    writer.writerow(["model_type", metrics.get("model_type", "")])
    writer.writerow(["mape", metrics.get("mape", "")])
    writer.writerow(["rmse", metrics.get("rmse", "")])
    return buffer.getvalue().encode("utf-8")


def export_forecast_pdf(payload: dict[str, Any]) -> bytes:
    rows = payload.get("periods", [])
    metrics = payload.get("metrics", {})
    body = "".join(
        f"<tr><td>{p['period_code']}</td><td>{p['predicted_inflow']:.2f}</td>"
        f"<td>{p['predicted_outflow']:.2f}</td><td>{p['predicted_net_cash_flow']:.2f}</td>"
        f"<td>{p['confidence_lower']:.2f}</td><td>{p['confidence_upper']:.2f}</td></tr>"
        for p in rows
    )
    html = f"""
    <html><body>
    <h1>Cash Flow Forecast</h1>
    <p>Model: {metrics.get('model_type', 'n/a')} | MAPE: {metrics.get('mape', 'n/a')}</p>
    <table border="1" cellpadding="4">
    <tr><th>Period</th><th>Inflow</th><th>Outflow</th><th>Net</th><th>Lower</th><th>Upper</th></tr>
    {body}
    </table>
    </body></html>
    """
    return export_to_pdf(html)
