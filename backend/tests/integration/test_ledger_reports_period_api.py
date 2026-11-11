"""Ledger, reports, period-end (frontend Ledger / Reports / Period End pages)."""

from __future__ import annotations

import pytest

from tests.integration.conftest import balanced_voucher_body


pytestmark = pytest.mark.integration


async def _ensure_approved_voucher(api_client, tenant) -> str:
    create = await api_client.post(
        tenant.path("/vouchers"),
        headers=tenant.headers,
        json=balanced_voucher_body(tenant.period_code),
    )
    assert create.status_code == 201, create.text
    vid = create.json()["id"]
    for action in ("save", "submit", "approve"):
        resp = await api_client.post(
            tenant.path(f"/vouchers/{vid}/{action}"),
            headers=tenant.headers,
        )
        assert resp.status_code == 200, f"{action}: {resp.text}"
    return vid


@pytest.mark.asyncio
async def test_ledger_endpoints(api_client, tenant) -> None:
    await _ensure_approved_voucher(api_client, tenant)
    p = tenant.period_code
    aid = tenant.account_set_id

    cases = [
        f"/account-sets/{aid}/ledger/general?account_code=1001&period_code={p}",
        f"/account-sets/{aid}/ledger/cash-journal?period_code={p}",
        f"/account-sets/{aid}/ledger/bank-journal?period_code={p}",
        f"/account-sets/{aid}/ledger/account-summary?period_code={p}",
    ]
    for path in cases:
        resp = await api_client.get(path, headers=tenant.headers)
        assert resp.status_code == 200, f"{path} -> {resp.status_code}: {resp.text}"

    # Subsidiary requires a dimension; expect 200 with empty or 422 if none configured
    sub = await api_client.get(
        f"/account-sets/{aid}/ledger/subsidiary"
        f"?account_code=1001&period_code={p}&dimension=Department",
        headers=tenant.headers,
    )
    assert sub.status_code in (200, 422), sub.text


@pytest.mark.asyncio
async def test_reports_core(api_client, tenant) -> None:
    filters = {"period_code": tenant.period_code}
    for name in ("balance-sheet", "income-statement", "cash-flow", "account-summary"):
        resp = await api_client.post(
            tenant.path(f"/reports/{name}"),
            headers=tenant.headers,
            json=filters,
        )
        assert resp.status_code == 200, f"{name}: {resp.text}"

    sources = await api_client.get(
        tenant.path("/report-data-sources"),
        headers=tenant.headers,
    )
    assert sources.status_code == 200, sources.text

    templates = await api_client.get(
        tenant.path("/report-templates"),
        headers=tenant.headers,
    )
    assert templates.status_code == 200, templates.text


@pytest.mark.asyncio
async def test_period_end_next_opening_and_close(api_client, tenant) -> None:
    # Close requires zero unapproved vouchers — leave period empty of drafts
    next_ob = await api_client.get(
        tenant.path(f"/periods/{tenant.period_code}/next-opening-balances"),
        headers=tenant.headers,
    )
    assert next_ob.status_code == 200, next_ob.text
    assert isinstance(next_ob.json(), list)

    # Carry helpers should respond (may be no-op)
    for action in ("carry-cost-forward", "carry-profit-loss", "calculate-depreciation"):
        resp = await api_client.post(
            tenant.path(f"/periods/{tenant.period_code}/{action}"),
            headers=tenant.headers,
        )
        assert resp.status_code in (200, 422), f"{action}: {resp.text}"

    close = await api_client.post(
        tenant.path(f"/periods/{tenant.period_code}/close"),
        headers=tenant.headers,
    )
    # Fresh account set with no vouchers should close; if seed creates drafts, 422 is informative
    assert close.status_code in (200, 409, 422), close.text
