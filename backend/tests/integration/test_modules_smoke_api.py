"""
Sidebar module smoke tests — endpoints each frontend page hits on load / primary actions.

Covers: cashier, payroll, assets, bank, payments, tax, ifrs, reconciliation, forecast, nlp.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_cashier_create_and_fx_balance(api_client, tenant) -> None:
    create = await api_client.post(
        tenant.path("/cashier/accounts"),
        headers=tenant.headers,
        json={
            "account_code": "1001",
            "cashier_type": "Cash",
            "name": "Petty Cash",
            "currency": "CNY",
        },
    )
    assert create.status_code in (200, 201), create.text

    fx = await api_client.get(
        tenant.path(f"/cashier/accounts/1001/fx-balance?period_code={tenant.period_code}"),
        headers=tenant.headers,
    )
    assert fx.status_code == 200, fx.text


@pytest.mark.asyncio
async def test_payroll_employees_list_and_create(api_client, tenant) -> None:
    listing = await api_client.get(
        tenant.path("/payroll/employees"),
        headers=tenant.headers,
    )
    assert listing.status_code == 200, listing.text
    assert isinstance(listing.json(), list)

    created = await api_client.post(
        tenant.path("/payroll/employees"),
        headers=tenant.headers,
        json={
            "name": "Test Employee",
            "department": "Finance",
            "base_salary": 8000,
        },
    )
    assert created.status_code in (200, 201, 422), created.text


@pytest.mark.asyncio
async def test_assets_register_list(api_client, tenant) -> None:
    resp = await api_client.get(
        tenant.path("/assets/register"),
        headers=tenant.headers,
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_bank_connections_list(api_client, tenant) -> None:
    resp = await api_client.get(
        tenant.path("/bank/connections"),
        headers=tenant.headers,
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_payments_queue_types_field_config(api_client, tenant) -> None:
    queue = await api_client.get(tenant.path("/payments/queue"), headers=tenant.headers)
    assert queue.status_code == 200, queue.text

    authorised = await api_client.get(
        tenant.path("/payments/authorised"),
        headers=tenant.headers,
    )
    assert authorised.status_code == 200, authorised.text

    types = await api_client.get(
        tenant.path("/payment-transaction-types"),
        headers=tenant.headers,
    )
    assert types.status_code == 200, types.text

    default = await api_client.get(
        tenant.path("/payment-transaction-types/default"),
        headers=tenant.headers,
    )
    assert default.status_code in (200, 404), default.text

    fields = await api_client.get(
        tenant.path(
            "/payment-field-config?routing_method=Domestic&settlement_method=BankTransfer"
        ),
        headers=tenant.headers,
    )
    assert fields.status_code in (200, 404, 422), fields.text

    routing = await api_client.get(
        tenant.path("/payments/routing-options?payment_type=domestic"),
        headers=tenant.headers,
    )
    assert routing.status_code in (200, 422), routing.text


@pytest.mark.asyncio
async def test_tax_filings_history(api_client, tenant) -> None:
    resp = await api_client.get(
        tenant.path("/tax/filings/history"),
        headers=tenant.headers,
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_ifrs_fair_value_adjustment(api_client, tenant) -> None:
    resp = await api_client.post(
        tenant.path("/ifrs/fair-value-adjustments"),
        headers=tenant.headers,
        json={
            "account_code": "1601",
            "period_code": tenant.period_code,
            "fair_value": 100000,
            "carrying_amount": 90000,
            "voucher_date": "2026-01-15",
        },
    )
    assert resp.status_code in (200, 201, 422), resp.text


@pytest.mark.asyncio
async def test_reconciliation_session_create(api_client, tenant) -> None:
    # Requires a bank connection_id — without one, expect 422
    resp = await api_client.post(
        tenant.path("/reconciliation/sessions"),
        headers=tenant.headers,
        json={
            "connection_id": "00000000-0000-0000-0000-000000000001",
            "period_code": tenant.period_code,
        },
    )
    assert resp.status_code in (200, 201, 404, 422), resp.text


@pytest.mark.asyncio
async def test_forecast_endpoints(api_client, tenant) -> None:
    for path in (
        tenant.path("/forecast"),
        tenant.path("/forecast/metrics"),
        tenant.path("/forecast/comparison"),
    ):
        resp = await api_client.get(path, headers=tenant.headers)
        # ML service may be unavailable locally — 200 empty or 503/501
        assert resp.status_code in (200, 404, 501, 503, 422), f"{path}: {resp.text}"


@pytest.mark.asyncio
async def test_nlp_chat_endpoint(api_client, tenant) -> None:
    resp = await api_client.post(
        "/nlp/chat",
        headers=tenant.headers,
        json={
            "message": "列出科目表",
            "account_set_id": tenant.account_set_id,
            "language": "zh",
        },
    )
    # NLP/vLLM often offline in local — accept gateway errors but not KeyError/500 from auth wiring
    assert resp.status_code in (200, 400, 422, 501, 503), resp.text
    if resp.status_code == 500:
        pytest.fail(f"NLP wiring crashed: {resp.text}")
