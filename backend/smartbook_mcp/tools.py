"""Read-only MCP tools wrapping existing SmartBook services."""

from __future__ import annotations

from typing import Any

from account_set import service as account_set_service
from auth.rbac import PERM_LEDGER, PERM_VOUCHERS
from chart_of_accounts import service as coa_service
from ledger import service as ledger_service
from platform.db_router import open_tenant_session
from smartbook_mcp.auth import (
    McpAuthError,
    assert_account_set_access,
    assert_permission,
    authenticate_user,
)
from smartbook_mcp.serialize import (
    account_set_summary,
    dumps_json,
    voucher_detail,
    voucher_summary,
)
from voucher import service as voucher_service


async def _prepare(account_set_id: str, permission: str) -> tuple[dict[str, Any], str]:
    user = await authenticate_user()
    await assert_permission(user, permission)
    aid = assert_account_set_access(user, account_set_id)
    return user, aid


def register_tools(mcp: Any) -> None:
    """Register the partial (read-only) SmartBook tool set on a FastMCP server."""

    @mcp.tool()
    async def list_account_sets() -> str:
        """List Account Sets accessible to the authenticated user (read-only)."""
        user = await authenticate_user()
        jwt_aid = str(user.get("account_set_id") or "")
        if not jwt_aid:
            raise McpAuthError("Token has no account_set_id; switch to an Account Set first.")
        async with open_tenant_session(jwt_aid) as db:
            rows = await account_set_service.list_account_sets(db, user_id=user["user_id"])
        return dumps_json([account_set_summary(r) for r in rows])

    @mcp.tool()
    async def get_account_tree(account_set_id: str) -> str:
        """Return the Chart of Accounts tree for an Account Set (read-only)."""
        _, aid = await _prepare(account_set_id, PERM_LEDGER)
        async with open_tenant_session(aid) as db:
            tree = await coa_service.get_account_tree(aid, db)
        return dumps_json({"account_set_id": aid, "accounts": tree})

    @mcp.tool()
    async def list_vouchers(
        account_set_id: str,
        period_code: str | None = None,
        status_filter: str | None = None,
    ) -> str:
        """List vouchers for an Account Set, optionally filtered by period/status (read-only)."""
        _, aid = await _prepare(account_set_id, PERM_VOUCHERS)
        async with open_tenant_session(aid) as db:
            rows = await voucher_service.list_vouchers(
                db,
                account_set_id=aid,
                period_code=period_code,
                status_filter=status_filter,
            )
        return dumps_json([voucher_summary(v) for v in rows])

    @mcp.tool()
    async def get_voucher(account_set_id: str, voucher_id: str) -> str:
        """Get one voucher with line entries (read-only)."""
        _, aid = await _prepare(account_set_id, PERM_VOUCHERS)
        async with open_tenant_session(aid) as db:
            voucher = await voucher_service.get_voucher(
                db, account_set_id=aid, voucher_id=voucher_id
            )
        return dumps_json(voucher_detail(voucher))

    @mcp.tool()
    async def get_account_summary(
        account_set_id: str,
        period_code: str,
        account_code: str | None = None,
    ) -> str:
        """Get period account summary balances (opening/debit/credit/closing) — read-only."""
        _, aid = await _prepare(account_set_id, PERM_LEDGER)
        async with open_tenant_session(aid) as db:
            summary = await ledger_service.get_account_summary(
                db,
                account_set_id=aid,
                period_code=period_code,
                account_code=account_code,
            )
        return dumps_json(summary)
