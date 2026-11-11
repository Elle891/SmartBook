"""
Integration test fixtures.

These tests exercise the real FastAPI app against local MySQL
(platform_registry + smartbook_shared). They are skipped unless
INTEGRATION=1 (set by scripts/integration-test.ps1).
"""

from __future__ import annotations

import os
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

PERIOD = "202601"


def _load_dev_env() -> None:
    env_file = REPO_ROOT / "scripts" / "dev.env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def pytest_configure(config: pytest.Config) -> None:
    _load_dev_env()
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("EMAIL_PROVIDER", "console")
    os.environ.setdefault(
        "SHARED_TENANT_DB_URL",
        "mysql+aiomysql://smartbook:smartbook@localhost:3306/smartbook_shared",
    )
    os.environ.setdefault(
        "DATABASE_URL",
        "mysql+aiomysql://smartbook:smartbook@localhost:3306/platform_registry",
    )
    os.environ.setdefault("JWT_ALGORITHM", "HS256")  # ignored by auth (RS256); harmless
    os.environ.pop("TENANT_DB_URL", None)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("INTEGRATION", "").strip() in ("1", "true", "yes"):
        return
    skip = pytest.mark.skip(reason="Set INTEGRATION=1 to run API integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def otp_capture(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Capture OTP plaintext from console email sender."""
    box: dict[str, str] = {}

    async def _capture(to: str, subject: str, body: str) -> None:
        box["to"] = to
        box["subject"] = subject
        box["body"] = body
        match = re.search(r"\b(\d{6})\b", body)
        if match:
            box["otp"] = match.group(1)

    monkeypatch.setattr("notifications.email.send_email", _capture)
    import notifications.email as email_mod

    monkeypatch.setattr(email_mod, "send_email", _capture)
    return box


@pytest.fixture
async def api_client(otp_capture: dict[str, str]):
    """httpx ASGI client bound to the FastAPI app (in-process)."""
    import httpx
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.otp_capture = otp_capture  # type: ignore[attr-defined]
        yield client


@pytest.fixture(scope="session", autouse=True)
async def ensure_shared_tenant_schema():
    """Create missing shared-tenant tables/columns so FE modules can connect."""
    # Import models so Base.metadata is complete
    import models.account  # noqa: F401
    import models.account_set  # noqa: F401
    import models.assets  # noqa: F401
    import models.bank  # noqa: F401
    import models.cashier  # noqa: F401
    import models.ledger  # noqa: F401
    import models.ml  # noqa: F401
    import models.nlp  # noqa: F401
    import models.payment  # noqa: F401
    import models.payroll  # noqa: F401
    import models.payroll_settings  # noqa: F401
    import models.report_engine  # noqa: F401
    import models.reports  # noqa: F401
    import models.smart_import  # noqa: F401
    import models.tenant_audit  # noqa: F401
    import models.voucher  # noqa: F401
    from models.base import Base
    from platform.db_router import _get_shared_tenant_engine
    from sqlalchemy import text

    engine = _get_shared_tenant_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        alters = [
            "ALTER TABLE payments ADD COLUMN recipient_agent_bic VARCHAR(11) NULL",
            "ALTER TABLE payments ADD COLUMN recipient_agent_name VARCHAR(255) NULL",
            "ALTER TABLE payments ADD COLUMN recipient_agent_address TEXT NULL",
            "ALTER TABLE payments ADD COLUMN intermediary_agent_bic VARCHAR(11) NULL",
            "ALTER TABLE payments ADD COLUMN exchange_rate DECIMAL(18,6) NULL",
            "ALTER TABLE payments ADD COLUMN charge_bearer VARCHAR(8) NULL",
            "ALTER TABLE payments ADD COLUMN payment_purpose_code VARCHAR(64) NULL",
            "ALTER TABLE payments ADD COLUMN remittance_info TEXT NULL",
            "ALTER TABLE payments ADD COLUMN end_to_end_id VARCHAR(64) NULL",
            "ALTER TABLE payments ADD COLUMN payment_scope VARCHAR(16) NOT NULL DEFAULT 'Domestic'",
            "ALTER TABLE payments ADD COLUMN actual_settlement_date DATE NULL",
            "ALTER TABLE payments ADD COLUMN bank_reference VARCHAR(128) NULL",
            "ALTER TABLE payments ADD COLUMN created_by CHAR(36) NULL",
            "ALTER TABLE payments ADD COLUMN updated_at DATETIME NULL",
            "ALTER TABLE nlp_interaction_logs ADD COLUMN user_message TEXT NULL",
            "ALTER TABLE nlp_interaction_logs ADD COLUMN response_text TEXT NULL",
            "ALTER TABLE nlp_interaction_logs ADD COLUMN confidence FLOAT NULL",
            "ALTER TABLE nlp_interaction_logs ADD COLUMN model_used VARCHAR(64) NULL",
            "ALTER TABLE nlp_interaction_logs ADD COLUMN rbac_check_passed TINYINT(1) NULL",
            "ALTER TABLE nlp_interaction_logs ADD COLUMN language VARCHAR(8) NULL",
        ]
        for stmt in alters:
            try:
                await conn.execute(text(stmt))
            except Exception:  # noqa: BLE001 — column already exists
                pass

    yield

    import platform.db_router as dr

    async def _safe_dispose(eng) -> None:
        if eng is None:
            return
        try:
            await eng.dispose()
        except Exception:  # noqa: BLE001
            pass

    for eng in list(dr._engine_pool.values()):
        await _safe_dispose(eng)
    dr._engine_pool.clear()
    await _safe_dispose(dr._shared_engine)
    dr._shared_engine = None
    await _safe_dispose(dr._platform_engine)
    dr._platform_engine = None


@pytest.fixture
def unique_email() -> str:
    return f"itest_{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture
def strong_password() -> str:
    return "Itest123!"


@dataclass
class AuthUser:
    email: str
    password: str
    user_id: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@dataclass
class TenantContext:
    user: AuthUser
    account_set_id: str
    journal_set_no: str
    period_code: str
    token: str
    role: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def path(self, suffix: str) -> str:
        suffix = suffix if suffix.startswith("/") else f"/{suffix}"
        return f"/account-sets/{self.account_set_id}{suffix}"


async def register_and_login(api_client, email: str, password: str) -> AuthUser:
    reg = await api_client.post(
        "/auth/register/email",
        json={
            "display_name": "Integration Tester",
            "email": email,
            "password": password,
        },
    )
    assert reg.status_code == 201, reg.text
    body = reg.json()
    otp = api_client.otp_capture.get("otp")
    assert otp and len(otp) == 6, f"OTP not captured: {api_client.otp_capture}"

    verify = await api_client.post(
        "/auth/register/verify-otp",
        json={
            "target": email,
            "session_id": body["session_id"],
            "otp": otp,
            "purpose": "register_email",
        },
    )
    assert verify.status_code == 200, verify.text

    login = await api_client.post(
        "/auth/login/email",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return AuthUser(
        email=email,
        password=password,
        user_id=str(body["user_id"]),
        token=token,
    )


async def create_and_switch_account_set(api_client, user: AuthUser) -> TenantContext:
    journal_no = f"IT{uuid.uuid4().hex[:8].upper()}"
    create = await api_client.post(
        "/account-sets",
        headers=user.headers,
        json={
            "name": f"ITest Set {journal_no}",
            "journal_set_no": journal_no,
            "status": "Active",
            "standard": "CAS",
            "base_currency": "CNY",
            "start_period": PERIOD,
            "datasource_type": "Shared",
        },
    )
    assert create.status_code == 201, create.text
    account_set_id = create.json()["id"]

    switched = await api_client.post(
        f"/account-sets/{account_set_id}/switch",
        headers=user.headers,
    )
    assert switched.status_code == 200, switched.text
    sw = switched.json()
    return TenantContext(
        user=user,
        account_set_id=account_set_id,
        journal_set_no=journal_no,
        period_code=PERIOD,
        token=sw["access_token"],
        role=sw.get("role", ""),
    )


@pytest.fixture
async def auth_user(api_client, unique_email: str, strong_password: str) -> AuthUser:
    return await register_and_login(api_client, unique_email, strong_password)


@pytest.fixture
async def tenant(api_client, auth_user: AuthUser) -> TenantContext:
    """Authenticated user with a switched CAS account set (Admin role)."""
    ctx = await create_and_switch_account_set(api_client, auth_user)
    assert ctx.role == "Account_Set_Admin"
    return ctx


def balanced_voucher_body(period_code: str = PERIOD) -> dict[str, Any]:
    return {
        "period_code": period_code,
        "type": "Receipt",
        "date": f"{period_code[:4]}-{period_code[4:6]}-15",
        "entries": [
            {
                "account_code": "1001",
                "debit_amount": 100,
                "credit_amount": 0,
                "description": "cash in",
            },
            {
                "account_code": "2001",
                "debit_amount": 0,
                "credit_amount": 100,
                "description": "loan",
            },
        ],
    }
