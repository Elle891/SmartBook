"""MCP authentication helpers — JWT + RBAC for read-only tools."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import HTTPException

from auth import rbac
from auth.jwt import verify_token

logger = logging.getLogger(__name__)


class McpAuthError(PermissionError):
    """Raised when an MCP caller is not authenticated or authorized."""


def resolve_token() -> str:
    """Resolve the bearer token from the environment (stdio / local agents)."""
    token = (
        os.environ.get("SMARTBOOK_MCP_TOKEN", "").strip()
        or os.environ.get("MCP_AUTH_TOKEN", "").strip()
    )
    if not token:
        raise McpAuthError(
            "Missing SMARTBOOK_MCP_TOKEN (or MCP_AUTH_TOKEN). "
            "Issue a JWT via /auth login and set it in the MCP process env."
        )
    return token


async def authenticate_user(*, skip_session: bool | None = None) -> dict[str, Any]:
    """Verify JWT and return the user context used by MCP tools."""
    token = resolve_token()
    try:
        payload = verify_token(token)
    except HTTPException as exc:
        raise McpAuthError(exc.detail) from exc

    user_id = str(payload.get("sub") or "")
    session_id = payload.get("session_id")
    if not user_id:
        raise McpAuthError("Token missing subject (sub).")

    if skip_session is None:
        skip_session = os.environ.get("SMARTBOOK_MCP_SKIP_SESSION", "").lower() in (
            "1",
            "true",
            "yes",
        )
        env = os.environ.get("ENVIRONMENT", "development").lower()
        if env in ("test", "development", "dev") and skip_session is False:
            # Default: skip Redis session for local MCP while JWT is still verified.
            skip_session = os.environ.get("SMARTBOOK_MCP_REQUIRE_SESSION", "").lower() not in (
                "1",
                "true",
                "yes",
            )

    if session_id and not skip_session:
        from auth.session import is_session_valid, touch_session

        try:
            if not await is_session_valid(str(session_id)):
                raise McpAuthError("Session expired due to inactivity.")
            await touch_session(user_id, str(session_id))
        except McpAuthError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("MCP session check failed (%s); continuing with JWT only", exc)

    return {
        "user_id": user_id,
        "account_set_id": str(payload.get("account_set_id") or ""),
        "role": str(payload.get("role") or ""),
        "session_id": str(session_id or ""),
    }


def assert_account_set_access(user: dict[str, Any], account_set_id: str) -> str:
    """Ensure the active JWT account set matches the requested one."""
    aid = str(account_set_id)
    jwt_aid = str(user.get("account_set_id") or "")
    if jwt_aid and jwt_aid != aid:
        raise McpAuthError(
            "account_set_id does not match the active Account Set in your token."
        )
    return aid


async def assert_permission(user: dict[str, Any], permission: str) -> None:
    """Enforce built-in / custom role permissions for an MCP tool."""
    role = str(user.get("role") or "")
    account_set_id = str(user.get("account_set_id") or "")
    permissions = await rbac.get_role_permissions(role, account_set_id)
    if permission not in permissions:
        raise McpAuthError(
            f"Permission '{permission}' required. Role '{role}' does not have it."
        )
