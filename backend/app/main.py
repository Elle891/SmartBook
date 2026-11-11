"""
svc-accounting — FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from platform.db_router import TenantDBMiddleware
from platform.logging_config import get_logger
from platform.otel_middleware import add_otel_middleware

logger = get_logger("svc-accounting")

app = FastAPI(
    title="Smart Accounting — svc-accounting",
    description="Core accounting platform API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production via env config
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenTelemetry span middleware
add_otel_middleware(app, service_name="svc-accounting")

# Tenant DB routing middleware — resolves async engine per request from JWT
app.add_middleware(TenantDBMiddleware)

# Prometheus metrics — exposes /metrics
Instrumentator().instrument(app).expose(app)

# ── Public auth routes (no JWT required) ─────────────────────────────────────
from auth.routes import router as auth_router  # noqa: E402

app.include_router(auth_router)

# ── Account Set Manager ───────────────────────────────────────────────────────
from account_set.routes import router as account_set_router  # noqa: E402

app.include_router(account_set_router)

# ── Chart of Accounts ─────────────────────────────────────────────────────────
from chart_of_accounts.routes import router as coa_router  # noqa: E402

app.include_router(coa_router)

# ── Voucher Engine ────────────────────────────────────────────────────────────
from voucher.routes import router as voucher_router  # noqa: E402

app.include_router(voucher_router)

# ── Ledger Engine ─────────────────────────────────────────────────────────────
from ledger.routes import router as ledger_router  # noqa: E402

app.include_router(ledger_router)

# ── Period-End Processor ──────────────────────────────────────────────────────
from period_end.routes import router as period_end_router  # noqa: E402

app.include_router(period_end_router)

# ── Cashier Module ──────────────────────────────────────────────────────────────
from cashier.routes import router as cashier_router  # noqa: E402

app.include_router(cashier_router)

# ── Payroll Module ──────────────────────────────────────────────────────────────
from payroll.routes import router as payroll_router  # noqa: E402

app.include_router(payroll_router)

# ── Fixed Asset Module ──────────────────────────────────────────────────────────
from assets.routes import router as assets_router  # noqa: E402

app.include_router(assets_router)

# ── Smart Import Module ─────────────────────────────────────────────────────────
from smart_import.routes import router as smart_import_router  # noqa: E402

app.include_router(smart_import_router)

# ── Invoice Scanner Module ────────────────────────────────────────────────────────
from invoice_scanner.routes import router as invoice_scanner_router  # noqa: E402

app.include_router(invoice_scanner_router)

# ── Report Engine ─────────────────────────────────────────────────────────────────
from reports.routes import router as reports_router  # noqa: E402

app.include_router(reports_router)

# ── Tax Module ────────────────────────────────────────────────────────────────────
from tax.routes import router as tax_router  # noqa: E402

app.include_router(tax_router)

# ── IFRS Compliance Module ────────────────────────────────────────────────────────
from ifrs.routes import router as ifrs_router  # noqa: E402

app.include_router(ifrs_router)

# ── Bank Integration Module ─────────────────────────────────────────────────────────
from bank.routes import router as bank_router  # noqa: E402

app.include_router(bank_router)

# ── Reconciliation Engine ─────────────────────────────────────────────────────────
from reconciliation.routes import router as reconciliation_router  # noqa: E402

app.include_router(reconciliation_router)

# ── Payment Hub ─────────────────────────────────────────────────────────────────────
from payment.routes import router as payment_router  # noqa: E402

app.include_router(payment_router)

# ── ML Forecast Engine ────────────────────────────────────────────────────────────
from ml.routes import router as ml_router  # noqa: E402

app.include_router(ml_router)

# ── NLP Assistant ───────────────────────────────────────────────────────────────────
from nlp.routes import router as nlp_router  # noqa: E402

app.include_router(nlp_router)

# ── Optional MCP (partial read-only tools for agents) ─────────────────────────
import os  # noqa: E402

if os.environ.get("SMARTBOOK_MCP_ENABLED", "").lower() in ("1", "true", "yes"):
    try:
        from smartbook_mcp.server import create_http_app  # noqa: E402

        app.mount("/mcp", create_http_app())
        logger.info("SmartBook MCP mounted at /mcp")
    except Exception as exc:  # noqa: BLE001
        logger.warning("SMARTBOOK_MCP_ENABLED set but MCP mount failed: %s", exc)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
