"""Auth + Account Set bootstrap (register / login / create / list / switch)."""

from __future__ import annotations

import uuid

import pytest

from tests.integration.conftest import create_and_switch_account_set, register_and_login


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_health(api_client) -> None:
    resp = await api_client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


@pytest.mark.asyncio
async def test_register_login_create_list_switch_account_set(
    api_client, unique_email: str, strong_password: str
) -> None:
    user = await register_and_login(api_client, unique_email, strong_password)
    ctx = await create_and_switch_account_set(api_client, user)

    listing = await api_client.get("/account-sets", headers=ctx.headers)
    assert listing.status_code == 200, listing.text
    items = listing.json()
    assert any(row["id"] == ctx.account_set_id for row in items)

    # Duplicate journal_set_no rejected
    dup = await api_client.post(
        "/account-sets",
        headers=user.headers,
        json={
            "name": "Dup",
            "journal_set_no": ctx.journal_set_no,
            "status": "Active",
            "standard": "CAS",
            "base_currency": "CNY",
            "start_period": "202601",
            "datasource_type": "Shared",
        },
    )
    assert dup.status_code == 422, dup.text


@pytest.mark.asyncio
async def test_login_invalid_credentials(api_client, unique_email: str, strong_password: str) -> None:
    resp = await api_client.post(
        "/auth/login/email",
        json={"email": unique_email, "password": strong_password},
    )
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.text or "detail" in resp.json()


@pytest.mark.asyncio
async def test_create_account_set_requires_auth(api_client) -> None:
    resp = await api_client.post(
        "/account-sets",
        json={
            "name": "No Auth",
            "journal_set_no": "NOAUTH1",
            "status": "Active",
            "standard": "CAS",
            "base_currency": "CNY",
            "start_period": "202601",
            "datasource_type": "Shared",
        },
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_password_reset_email_flow(api_client, auth_user, strong_password: str) -> None:
    new_password = "ItestReset9!"
    init = await api_client.post(
        "/auth/password-reset/email",
        json={"email": auth_user.email},
    )
    assert init.status_code == 200, init.text
    session_id = init.json().get("session_id")
    assert session_id
    otp = api_client.otp_capture.get("otp")
    assert otp and len(otp) == 6, api_client.otp_capture

    verify = await api_client.post(
        "/auth/password-reset/verify-otp",
        json={
            "target": auth_user.email,
            "session_id": session_id,
            "otp": otp,
            "purpose": "reset_email",
            "new_password": new_password,
        },
    )
    assert verify.status_code == 200, verify.text

    bad = await api_client.post(
        "/auth/login/email",
        json={"email": auth_user.email, "password": strong_password},
    )
    assert bad.status_code == 401

    ok = await api_client.post(
        "/auth/login/email",
        json={"email": auth_user.email, "password": new_password},
    )
    assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_account_set_roles_and_members(api_client, tenant) -> None:
    roles = await api_client.get(tenant.path("/roles"), headers=tenant.headers)
    assert roles.status_code == 200, roles.text
    role_list = roles.json()
    assert isinstance(role_list, list)
    assert len(role_list) >= 1

    members = await api_client.get(tenant.path("/members"), headers=tenant.headers)
    assert members.status_code == 200, members.text
    member_list = members.json()
    assert any(str(m.get("user_id")) == tenant.user.user_id for m in member_list)

    custom = await api_client.post(
        tenant.path("/roles"),
        headers=tenant.headers,
        json={
            "name": f"Custom_{uuid.uuid4().hex[:6]}",
            "permissions": ["ledger", "reports"],
        },
    )
    assert custom.status_code == 201, custom.text


@pytest.mark.asyncio
async def test_opening_balances(api_client, tenant) -> None:
    resp = await api_client.post(
        tenant.path("/opening-balances"),
        headers=tenant.headers,
        json={
            "entries": [
                {"account_code": "1001", "debit_amount": 1000, "credit_amount": 0},
                {"account_code": "3001", "debit_amount": 0, "credit_amount": 1000},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert float(body["total_debits"]) == float(body["total_credits"])
