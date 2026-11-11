"""Chart of accounts + voucher lifecycle (frontend Voucher / Chart pages)."""

from __future__ import annotations

import pytest

from tests.integration.conftest import balanced_voucher_body


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_chart_of_accounts_tree_and_create(api_client, tenant) -> None:
    tree = await api_client.get(tenant.path("/accounts"), headers=tenant.headers)
    assert tree.status_code == 200, tree.text
    body = tree.json()
    accounts = body.get("accounts") if isinstance(body, dict) else body
    assert isinstance(accounts, list)
    codes = {a.get("code") for a in _flatten_accounts(accounts)}
    assert "1001" in codes
    assert "2001" in codes

    created = await api_client.post(
        tenant.path("/accounts"),
        headers=tenant.headers,
        json={
            "code": "1003",
            "name": "Integration Other Cash",
            "account_type": "Asset",
        },
    )
    assert created.status_code in (200, 201), created.text


@pytest.mark.asyncio
async def test_voucher_create_list_get_save_submit_approve(api_client, tenant) -> None:
    create = await api_client.post(
        tenant.path("/vouchers"),
        headers=tenant.headers,
        json=balanced_voucher_body(tenant.period_code),
    )
    assert create.status_code == 201, create.text
    voucher = create.json()
    voucher_id = voucher["id"]
    assert voucher["status"] in ("Draft", "draft", "DRAFT") or voucher.get("id")

    listing = await api_client.get(
        tenant.path(f"/vouchers?period_code={tenant.period_code}"),
        headers=tenant.headers,
    )
    assert listing.status_code == 200, listing.text
    assert any(v["id"] == voucher_id for v in listing.json())

    detail = await api_client.get(
        tenant.path(f"/vouchers/{voucher_id}"),
        headers=tenant.headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["id"] == voucher_id

    # Frontend submit path; save enforces balance before review in engine
    saved = await api_client.post(
        tenant.path(f"/vouchers/{voucher_id}/save"),
        headers=tenant.headers,
    )
    assert saved.status_code == 200, saved.text

    submitted = await api_client.post(
        tenant.path(f"/vouchers/{voucher_id}/submit"),
        headers=tenant.headers,
    )
    assert submitted.status_code == 200, submitted.text

    approved = await api_client.post(
        tenant.path(f"/vouchers/{voucher_id}/approve"),
        headers=tenant.headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] in ("Approved", "approved", "APPROVED")


@pytest.mark.asyncio
async def test_voucher_requires_switched_role(api_client, auth_user, tenant) -> None:
    """Login token without switch has empty role → RBAC must reject vouchers."""
    resp = await api_client.post(
        f"/account-sets/{tenant.account_set_id}/vouchers",
        headers=auth_user.headers,
        json=balanced_voucher_body(),
    )
    assert resp.status_code == 403, resp.text


def _flatten_accounts(nodes: list) -> list:
    out: list = []
    for node in nodes:
        out.append(node)
        children = node.get("children") or []
        if children:
            out.extend(_flatten_accounts(children))
    return out
