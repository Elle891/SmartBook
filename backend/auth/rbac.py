"""
Per-Account_Set RBAC — role resolution and permission enforcement.

Built-in roles and their permission sets are defined here.
Custom roles are stored in the AccountSetRole table (task 5).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, HTTPException, status

logger = logging.getLogger(__name__)

# ── Permission constants ──────────────────────────────────────────────────────

PERM_VOUCHERS = "vouchers"
PERM_CASHIER = "cashier"
PERM_INVOICES = "invoices"
PERM_PAYROLL = "payroll"
PERM_ASSETS = "assets"
PERM_TAX = "tax"
PERM_PERIOD_END = "period_end"
PERM_LEDGER = "ledger"
PERM_REPORTS = "reports"
PERM_CREATE_ACCOUNT_SET = "create_account_set"
PERM_DELETE_ACCOUNT_SET = "delete_account_set"
PERM_BACKUP_RESTORE = "backup_restore"
PERM_REINITIALIZE = "reinitialize"
PERM_LINK_INVENTORY = "link_inventory"
PERM_LINK_CLOUD_INVOICES = "link_cloud_invoices"
PERM_USER_MANAGEMENT = "user_management"
PERM_AUDIT_LOG = "audit_log"

# ── Built-in role definitions ─────────────────────────────────────────────────

ROLE_ACCOUNT_SET_ADMIN = "Account_Set_Admin"
ROLE_SUPERVISOR = "Supervisor"
ROLE_VOUCHER_CLERK = "Voucher_Clerk"
ROLE_CASHIER = "Cashier"
ROLE_VIEWER = "Viewer"

_BUILTIN_PERMISSIONS: dict[str, list[str]] = {
    ROLE_ACCOUNT_SET_ADMIN: [
        PERM_VOUCHERS, PERM_CASHIER, PERM_INVOICES, PERM_PAYROLL, PERM_ASSETS,
        PERM_TAX, PERM_PERIOD_END, PERM_LEDGER, PERM_REPORTS,
        PERM_CREATE_ACCOUNT_SET, PERM_DELETE_ACCOUNT_SET, PERM_BACKUP_RESTORE,
        PERM_REINITIALIZE, PERM_LINK_INVENTORY, PERM_LINK_CLOUD_INVOICES,
        PERM_USER_MANAGEMENT, PERM_AUDIT_LOG,
    ],
    ROLE_SUPERVISOR: [
        PERM_VOUCHERS, PERM_CASHIER, PERM_INVOICES, PERM_PAYROLL, PERM_ASSETS,
        PERM_TAX, PERM_PERIOD_END, PERM_LEDGER, PERM_REPORTS,
        PERM_CREATE_ACCOUNT_SET,
    ],
    ROLE_VOUCHER_CLERK: [
        PERM_VOUCHERS, PERM_INVOICES, PERM_PAYROLL, PERM_ASSETS, PERM_TAX,
        PERM_PERIOD_END, PERM_LEDGER, PERM_REPORTS, PERM_CREATE_ACCOUNT_SET,
    ],
    ROLE_CASHIER: [
        PERM_CASHIER, PERM_VOUCHERS, PERM_ASSETS, PERM_LEDGER, PERM_REPORTS,
        PERM_CREATE_ACCOUNT_SET,
    ],
    ROLE_VIEWER: [
        PERM_VOUCHERS, PERM_CASHIER, PERM_ASSETS, PERM_LEDGER, PERM_REPORTS,
        PERM_CREATE_ACCOUNT_SET,
    ],
}


# ── Role resolution ───────────────────────────────────────────────────────────


async def get_user_role(user_id: str, account_set_id: str) -> str:
    """Look up the user's role within the given Account Set.

    Queries the AccountSetMember table.  The model is defined in task 5;
    until then this function stubs the DB lookup and returns a default role.

    TODO (task 5): replace stub with real DB query:
        SELECT role_name FROM account_set_members
        WHERE user_id = :user_id AND account_set_id = :account_set_id
    """
    # Stub: return Viewer as the safe default until models exist.
    logger.debug(
        "get_user_role stub called for user=%s account_set=%s — returning Viewer",
        user_id,
        account_set_id,
    )
    return ROLE_VIEWER


async def get_role_permissions(role_name: str, account_set_id: str) -> list[str]:
    """Return the permission list for a role.

    Checks built-in roles first; falls back to custom roles stored in
    AccountSetRole (task 5 model).

    TODO (task 5): query AccountSetRole.permissions for custom roles.
    """
    if role_name in _BUILTIN_PERMISSIONS:
        return _BUILTIN_PERMISSIONS[role_name]

    # Stub for custom roles until AccountSetRole model exists.
    logger.warning(
        "Custom role '%s' for account_set=%s — no DB model yet, returning []",
        role_name,
        account_set_id,
    )
    return []


# ── FastAPI dependency factory ────────────────────────────────────────────────


def require_permission(permission: str):  # noqa: ANN201
    """Return a FastAPI dependency that enforces the given permission.

    Usage::

        @router.get("/vouchers")
        async def list_vouchers(
            _: None = Depends(require_permission(PERM_VOUCHERS)),
            user: dict = Depends(get_current_user),
        ):
            ...
    """

    async def _check(
        user: dict[str, Any] = Depends(_get_current_user_dep()),
    ) -> None:
        role: str = user.get("role", "")
        account_set_id: str = user.get("account_set_id", "")

        permissions = await get_role_permissions(role, account_set_id)
        if permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Permission '{permission}' required. "
                    f"Your role '{role}' does not have this permission."
                ),
            )

    return _check


def _get_current_user_dep():  # noqa: ANN201
    """Lazy import to avoid circular dependency with jwt module."""
    from auth.jwt import get_current_user

    return get_current_user
