"""Unit tests for partial SmartBook MCP support (read-only tools)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from smartbook_mcp.auth import (
    McpAuthError,
    assert_account_set_access,
    assert_permission,
    authenticate_user,
    resolve_token,
)
from smartbook_mcp.serialize import dumps_json, voucher_detail, voucher_summary
from smartbook_mcp.tools import register_tools


class TestSerialize:
    def test_dumps_json_uuid_and_decimal(self):
        import uuid
        from decimal import Decimal

        text = dumps_json({"id": uuid.UUID(int=1), "amt": Decimal("12.50")})
        data = json.loads(text)
        assert data["id"].endswith("0001")
        assert data["amt"] == 12.5

    def test_voucher_summary_and_detail(self):
        voucher = SimpleNamespace(
            id="v1",
            account_set_id="a1",
            period_code="202601",
            voucher_number=3,
            type="Transfer",
            date=None,
            status="Approved",
            created_by="u1",
            reviewed_by=None,
            rejection_reason=None,
            entries=[
                SimpleNamespace(
                    id="e1",
                    account_code="1001",
                    debit_amount=100,
                    credit_amount=0,
                    description="cash",
                    aux_dimension_values={},
                    sequence=1,
                )
            ],
        )
        summary = voucher_summary(voucher)
        assert summary["voucher_number"] == 3
        detail = voucher_detail(voucher)
        assert detail["entries"][0]["debit_amount"] == 100.0


class TestAuth:
    def test_resolve_token_missing(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("SMARTBOOK_MCP_TOKEN", raising=False)
        monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
        with pytest.raises(McpAuthError):
            resolve_token()

    def test_resolve_token_ok(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SMARTBOOK_MCP_TOKEN", "abc.jwt.token")
        assert resolve_token() == "abc.jwt.token"

    def test_assert_account_set_mismatch(self):
        with pytest.raises(McpAuthError):
            assert_account_set_access(
                {"account_set_id": "aaa"},
                "bbb",
            )

    def test_assert_account_set_match(self):
        assert assert_account_set_access({"account_set_id": "aaa"}, "aaa") == "aaa"

    @pytest.mark.asyncio
    async def test_assert_permission_denied(self):
        with patch(
            "smartbook_mcp.auth.rbac.get_role_permissions",
            new=AsyncMock(return_value=["ledger"]),
        ):
            with pytest.raises(McpAuthError):
                await assert_permission(
                    {"role": "Viewer", "account_set_id": "a1"},
                    "vouchers",
                )

    @pytest.mark.asyncio
    async def test_authenticate_user_ok(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SMARTBOOK_MCP_TOKEN", "tok")
        monkeypatch.setenv("ENVIRONMENT", "test")
        with patch(
            "smartbook_mcp.auth.verify_token",
            return_value={
                "sub": "user-1",
                "account_set_id": "as-1",
                "role": "Viewer",
                "session_id": "sess-1",
            },
        ):
            user = await authenticate_user(skip_session=True)
        assert user["user_id"] == "user-1"
        assert user["account_set_id"] == "as-1"


class TestToolsRegistered:
    def test_register_tools_exposes_five_read_only_tools(self):
        mcp = MagicMock()
        # @mcp.tool() is used as a decorator factory
        def tool_decorator():
            def wrapper(fn):
                mcp._tools.append(fn.__name__)
                return fn

            return wrapper

        mcp.tool = tool_decorator
        mcp._tools = []
        register_tools(mcp)
        assert mcp._tools == [
            "list_account_sets",
            "get_account_tree",
            "list_vouchers",
            "get_voucher",
            "get_account_summary",
        ]


class TestCreateMcp:
    def test_create_mcp_builds_server(self):
        from smartbook_mcp.server import create_mcp

        mcp = create_mcp()
        assert mcp.name == "smartbook"
        assert hasattr(mcp, "run")
        assert hasattr(mcp, "streamable_http_app")


class TestListVouchersTool:
    @pytest.mark.asyncio
    async def test_list_vouchers_calls_service(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SMARTBOOK_MCP_TOKEN", "tok")
        monkeypatch.setenv("ENVIRONMENT", "test")

        voucher = SimpleNamespace(
            id="v1",
            account_set_id="as-1",
            period_code="202601",
            voucher_number=1,
            type="Receipt",
            date=None,
            status="Draft",
            created_by="u1",
            reviewed_by=None,
            rejection_reason=None,
        )

        fake_session = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=fake_session)
        cm.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "smartbook_mcp.tools.authenticate_user",
                new=AsyncMock(
                    return_value={
                        "user_id": "u1",
                        "account_set_id": "as-1",
                        "role": "Viewer",
                    }
                ),
            ),
            patch(
                "smartbook_mcp.tools.assert_permission",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "smartbook_mcp.tools.open_tenant_session",
                return_value=cm,
            ),
            patch(
                "smartbook_mcp.tools.voucher_service.list_vouchers",
                new=AsyncMock(return_value=[voucher]),
            ),
        ):
            mcp = MagicMock()
            captured = {}

            def tool_decorator():
                def wrapper(fn):
                    captured[fn.__name__] = fn
                    return fn

                return wrapper

            mcp.tool = tool_decorator
            register_tools(mcp)
            result = await captured["list_vouchers"]("as-1", period_code="202601")
            data = json.loads(result)
            assert data[0]["id"] == "v1"
            assert data[0]["period_code"] == "202601"
