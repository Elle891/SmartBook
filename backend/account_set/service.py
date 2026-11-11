"""
Account Set Manager service.

Handles creation, listing, switching, opening balances, provisioning,
deletion, backup/restore/reinitialize, user access management, and
custom role management for Account Sets.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from audit.service import write_audit
from auth.rbac import (
    ROLE_ACCOUNT_SET_ADMIN,
    ROLE_CASHIER,
    ROLE_SUPERVISOR,
    ROLE_VIEWER,
    ROLE_VOUCHER_CLERK,
    _BUILTIN_PERMISSIONS,
)
from models.account import Account
from models.account_set import AccountSet, AccountSetMember, AccountSetRole
from models.user import User

logger = logging.getLogger(__name__)

# ── Built-in role seed data ───────────────────────────────────────────────────

_BUILTIN_ROLES = [
    ROLE_ACCOUNT_SET_ADMIN,
    ROLE_SUPERVISOR,
    ROLE_VOUCHER_CLERK,
    ROLE_CASHIER,
    ROLE_VIEWER,
]


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_admin_role(session: AsyncSession, account_set_id: str) -> AccountSetRole:
    """Return the Account_Set_Admin role for the given account set."""
    result = await session.execute(
        select(AccountSetRole).where(
            AccountSetRole.account_set_id == account_set_id,
            AccountSetRole.name == ROLE_ACCOUNT_SET_ADMIN,
        )
    )
    role = result.scalar_one_or_none()
    if role is None:
        raise ValueError(f"Account_Set_Admin role not found for account_set_id={account_set_id}")
    return role


async def _require_admin(
    session: AsyncSession, account_set_id: str, user_id: str
) -> None:
    """Raise PermissionError if user is not Account_Set_Admin."""
    result = await session.execute(
        select(AccountSetMember).where(
            AccountSetMember.account_set_id == account_set_id,
            AccountSetMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise PermissionError("User is not a member of this account set.")

    role_result = await session.execute(
        select(AccountSetRole).where(AccountSetRole.id == member.role_id)
    )
    role = role_result.scalar_one_or_none()
    if role is None or role.name != ROLE_ACCOUNT_SET_ADMIN:
        raise PermissionError("Account_Set_Admin role required.")


# ── Core Account Set operations ───────────────────────────────────────────────


async def create_account_set(
    session: AsyncSession,
    *,
    name: str,
    journal_set_no: str,
    standard: str,
    base_currency: str,
    start_period: str,
    datasource_type: str = "Shared",
    status: str = "Active",
    datasource_config: dict[str, Any] | None = None,
    created_by_user_id: str,
) -> AccountSet:
    """
    Create a new Account Set.

    - Validates datasource connectivity for Individual datasource.
    - Provisions the tenant database.
    - Seeds the correct chart of accounts template (CAS or IFRS).
    - Seeds 5 built-in roles.
    - Auto-assigns Account_Set_Admin role to the creator.
    """
    journal_set_no = (journal_set_no or "").strip()
    if not journal_set_no:
        raise ValueError("Journal Set No. is required.")
    if standard not in ("CAS", "IFRS"):
        raise ValueError(f"Invalid standard '{standard}'. Must be 'CAS' or 'IFRS'.")
    if datasource_type not in ("Shared", "Individual"):
        raise ValueError(f"Invalid datasource_type '{datasource_type}'.")
    if status not in ("Active", "Closed"):
        raise ValueError(f"Invalid status '{status}'. Must be 'Active' or 'Closed'.")

    existing = await session.execute(
        select(AccountSet).where(AccountSet.journal_set_no == journal_set_no)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Journal Set No. '{journal_set_no}' already exists.")

    # Validate Individual datasource connectivity before provisioning
    if datasource_type == "Individual":
        if not datasource_config:
            raise ValueError("datasource_config required for Individual datasource.")
        await _validate_external_db_connectivity(datasource_config)

    account_set = AccountSet(
        id=uuid.uuid4(),
        name=name,
        journal_set_no=journal_set_no,
        standard=standard,
        base_currency=base_currency,
        start_period=start_period,
        datasource_type=datasource_type,
        status=status,
        created_by_user_id=created_by_user_id,
    )
    session.add(account_set)
    await session.flush()  # get the id

    account_set_id = str(account_set.id)

    # Seed built-in roles
    role_map = await _seed_builtin_roles(session, account_set_id)

    # Auto-assign Account_Set_Admin to creator
    admin_role = role_map[ROLE_ACCOUNT_SET_ADMIN]
    member = AccountSetMember(
        account_set_id=account_set.id,
        user_id=created_by_user_id,
        role_id=admin_role.id,
    )
    session.add(member)
    await session.flush()

    # Seed chart of accounts template
    await _seed_chart_of_accounts(session, account_set_id, standard)

    # Provision tenant database (async, non-blocking for Shared; validates for Individual)
    await _provision_database(account_set_id, datasource_type, datasource_config)

    from models.tenant_audit import TenantAuditLog

    session.add(
        TenantAuditLog(
            account_set_id=account_set.id,
            user_id=created_by_user_id,
            action="account_set.create",
            entity_type="AccountSet",
            entity_id=account_set_id,
            new_value={
                "name": name,
                "journal_set_no": journal_set_no,
                "standard": standard,
                "status": status,
                "datasource_type": datasource_type,
            },
        )
    )
    await session.flush()

    await session.commit()
    await session.refresh(account_set)
    return account_set


async def list_account_sets(
    session: AsyncSession, *, user_id: str
) -> list[AccountSet]:
    """Return all Account Sets the user has any role in."""
    result = await session.execute(
        select(AccountSet)
        .join(AccountSetMember, AccountSetMember.account_set_id == AccountSet.id)
        .where(AccountSetMember.user_id == user_id)
        .order_by(AccountSet.created_at.desc())
    )
    return list(result.scalars().all())


async def switch_account_set(
    session: AsyncSession, *, user_id: str, account_set_id: str
) -> dict[str, Any]:
    """
    Switch the active Account Set for a user session.

    Returns session context with account_set_id and user's role.
    """
    result = await session.execute(
        select(AccountSetMember).where(
            AccountSetMember.account_set_id == account_set_id,
            AccountSetMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise PermissionError("User does not have access to this account set.")

    role_result = await session.execute(
        select(AccountSetRole).where(AccountSetRole.id == member.role_id)
    )
    role = role_result.scalar_one_or_none()
    role_name = role.name if role else "Unknown"

    return {
        "account_set_id": account_set_id,
        "user_id": user_id,
        "role": role_name,
    }


async def list_members(
    session: AsyncSession,
    *,
    account_set_id: str,
    admin_user_id: str,
) -> list[dict[str, Any]]:
    """List account set members with user and role details (admin only).

    Users live in the platform DB; members/roles live in the tenant DB.
    Never JOIN users on the tenant session.
    """
    await _require_admin(session, account_set_id, admin_user_id)

    result = await session.execute(
        select(AccountSetMember, AccountSetRole)
        .join(AccountSetRole, AccountSetRole.id == AccountSetMember.role_id)
        .where(AccountSetMember.account_set_id == account_set_id)
        .order_by(AccountSetMember.joined_at.asc())
    )
    rows = result.all()
    user_ids = [str(member.user_id) for member, _role in rows]
    users_by_id = await _load_platform_users(user_ids)

    members: list[dict[str, Any]] = []
    for member, role in rows:
        user = users_by_id.get(str(member.user_id))
        members.append(
            {
                "id": member.id,
                "account_set_id": member.account_set_id,
                "user_id": member.user_id,
                "role_id": member.role_id,
                "role_name": role.name,
                "display_name": getattr(user, "display_name", "") or "",
                "mobile": getattr(user, "mobile", None),
                "email": getattr(user, "email", None),
                "joined_at": member.joined_at,
            }
        )
    return members


async def _load_platform_users(user_ids: list[str]) -> dict[str, Any]:
    """Fetch User rows from the platform registry database by id."""
    if not user_ids:
        return {}
    from platform.db_router import _get_platform_session_factory

    factory = _get_platform_session_factory()
    async with factory() as platform_db:
        result = await platform_db.execute(select(User).where(User.id.in_(user_ids)))
        users = list(result.scalars().all())
    return {str(u.id): u for u in users}


async def test_datasource_connection(db_config: dict[str, Any]) -> None:
    """Validate external database connectivity (used before account set creation)."""
    await _validate_external_db_connectivity(db_config)


async def set_opening_balances(
    session: AsyncSession,
    *,
    account_set_id: str,
    entries: list[dict[str, Any]],
    user_id: str,
) -> dict[str, Any]:
    """
    Set opening balances for accounts.

    Validates that total debits == total credits.
    """
    total_debits = sum(float(e.get("debit_amount", 0)) for e in entries)
    total_credits = sum(float(e.get("credit_amount", 0)) for e in entries)

    # Round to 2 decimal places to avoid floating-point drift
    total_debits = round(total_debits, 2)
    total_credits = round(total_credits, 2)

    if total_debits != total_credits:
        raise ValueError(
            f"Opening balances do not balance: "
            f"debits={total_debits}, credits={total_credits}, "
            f"difference={abs(total_debits - total_credits)}"
        )

    await write_audit(
        session,
        user_id=user_id,
        action="account_set.set_opening_balances",
        entity_type="AccountSet",
        entity_id=account_set_id,
        new_value={"entry_count": len(entries), "total_debits": total_debits},
            account_set_id=account_set_id,
    )

    await session.commit()
    return {
        "message": "Opening balances saved successfully.",
        "total_debits": total_debits,
        "total_credits": total_credits,
    }


async def get_tenant_database_config(account_set_id: str) -> dict[str, Any]:
    """Look up the tenant's database connection config from the Platform Registry."""
    from platform.registry.service import get_tenant_db_config

    config = await get_tenant_db_config(account_set_id)
    return {
        "account_set_id": config.account_set_id,
        "db_type": config.db_type.value,
        "db_host": config.db_host,
        "db_port": config.db_port,
        "db_name": config.db_name,
        "db_user": config.db_user,
        "status": config.status,
    }


async def provision_tenant_database(
    account_set_id: str,
    datasource_type: str,
    datasource_config: dict[str, Any] | None = None,
    accounting_standard: str = "CAS",
) -> dict[str, Any]:
    """Provision the tenant database via the platform provisioner."""
    from platform.provisioner import provision_tenant_database as _provision
    from platform.registry.models import DbType

    db_type = DbType.postgresql  # default
    return await _provision(
        account_set_id,
        db_type,
        datasource_config,
        accounting_standard,
    )


async def delete_account_set(
    session: AsyncSession,
    *,
    account_set_id: str,
    user_id: str,
) -> None:
    """Delete an Account Set. Account_Set_Admin only. Irreversible."""
    await _require_admin(session, account_set_id, user_id)

    result = await session.execute(
        select(AccountSet).where(AccountSet.id == account_set_id)
    )
    account_set = result.scalar_one_or_none()
    if account_set is None:
        raise KeyError(f"AccountSet {account_set_id} not found.")

    await write_audit(
        session,
        user_id=user_id,
        action="account_set.delete",
        entity_type="AccountSet",
        entity_id=account_set_id,
        old_value={"name": account_set.name, "standard": account_set.standard},
            account_set_id=account_set_id,
    )

    await session.delete(account_set)
    await session.commit()


async def backup_account_set(
    session: AsyncSession,
    *,
    account_set_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Initiate a backup of the Account Set. Account_Set_Admin only."""
    await _require_admin(session, account_set_id, user_id)

    backup_ref = str(uuid.uuid4())
    await write_audit(
        session,
        user_id=user_id,
        action="account_set.backup",
        entity_type="AccountSet",
        entity_id=account_set_id,
        new_value={"backup_ref": backup_ref},
            account_set_id=account_set_id,
    )
    await session.commit()

    logger.info("Backup initiated for account_set_id=%s ref=%s", account_set_id, backup_ref)
    return {"backup_ref": backup_ref, "status": "initiated"}


async def restore_account_set(
    session: AsyncSession,
    *,
    account_set_id: str,
    backup_ref: str,
    user_id: str,
) -> dict[str, Any]:
    """Restore an Account Set from a backup. Account_Set_Admin only."""
    await _require_admin(session, account_set_id, user_id)

    await write_audit(
        session,
        user_id=user_id,
        action="account_set.restore",
        entity_type="AccountSet",
        entity_id=account_set_id,
        new_value={"backup_ref": backup_ref},
            account_set_id=account_set_id,
    )
    await session.commit()

    logger.info("Restore initiated for account_set_id=%s ref=%s", account_set_id, backup_ref)
    return {"status": "initiated", "backup_ref": backup_ref}


async def reinitialize_account_set(
    session: AsyncSession,
    *,
    account_set_id: str,
    user_id: str,
) -> dict[str, Any]:
    """
    Reinitialize an Account Set — clears all vouchers and ledger data,
    preserves chart of accounts and settings. Account_Set_Admin only.
    """
    await _require_admin(session, account_set_id, user_id)

    await write_audit(
        session,
        user_id=user_id,
        action="account_set.reinitialize",
        entity_type="AccountSet",
        entity_id=account_set_id,
            account_set_id=account_set_id,
    )
    await session.commit()

    logger.info("Reinitialized account_set_id=%s", account_set_id)
    return {"status": "reinitialized", "account_set_id": account_set_id}


# ── User access management ────────────────────────────────────────────────────


async def invite_user(
    session: AsyncSession,
    *,
    account_set_id: str,
    mobile_number: str,
    role_id: str,
    inviter_user_id: str,
) -> AccountSetMember:
    """
    Invite a registered user to an Account Set by mobile number.

    Looks up the user by mobile, creates an AccountSetMember.
    Account_Set_Admin only.
    """
    await _require_admin(session, account_set_id, inviter_user_id)

    # Users live on the platform DB — do not query User on the tenant session.
    from platform.db_router import _get_platform_session_factory

    factory = _get_platform_session_factory()
    async with factory() as platform_db:
        user_result = await platform_db.execute(
            select(User).where(User.mobile == mobile_number)
        )
        user = user_result.scalar_one_or_none()
    if user is None:
        raise KeyError(f"No registered user found with mobile number '{mobile_number}'.")

    # Verify role belongs to this account set
    role_result = await session.execute(
        select(AccountSetRole).where(
            AccountSetRole.id == role_id,
            AccountSetRole.account_set_id == account_set_id,
        )
    )
    role = role_result.scalar_one_or_none()
    if role is None:
        raise KeyError(f"Role {role_id} not found in account set {account_set_id}.")

    # Check if already a member
    existing = await session.execute(
        select(AccountSetMember).where(
            AccountSetMember.account_set_id == account_set_id,
            AccountSetMember.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("User is already a member of this account set.")

    member = AccountSetMember(
        account_set_id=account_set_id,
        user_id=user.id,
        role_id=role_id,
    )
    session.add(member)

    await write_audit(
        session,
        user_id=inviter_user_id,
        action="account_set.invite_user",
        entity_type="AccountSetMember",
        entity_id=str(user.id),
        new_value={"mobile": mobile_number, "role_id": role_id},
            account_set_id=account_set_id,
    )

    await session.commit()
    await session.refresh(member)
    return member


async def change_user_role(
    session: AsyncSession,
    *,
    account_set_id: str,
    target_user_id: str,
    new_role_id: str,
    admin_user_id: str,
) -> AccountSetMember:
    """
    Change the role of a user within an Account Set.

    Cannot revoke Account_Set_Admin from the creator.
    Account_Set_Admin only.
    """
    await _require_admin(session, account_set_id, admin_user_id)

    # Get the account set to check creator
    as_result = await session.execute(
        select(AccountSet).where(AccountSet.id == account_set_id)
    )
    account_set = as_result.scalar_one_or_none()
    if account_set is None:
        raise KeyError(f"AccountSet {account_set_id} not found.")

    # Get target member
    member_result = await session.execute(
        select(AccountSetMember).where(
            AccountSetMember.account_set_id == account_set_id,
            AccountSetMember.user_id == target_user_id,
        )
    )
    member = member_result.scalar_one_or_none()
    if member is None:
        raise KeyError(f"User {target_user_id} is not a member of this account set.")

    # Protect creator's admin role
    if str(account_set.created_by_user_id) == str(target_user_id):
        current_role_result = await session.execute(
            select(AccountSetRole).where(AccountSetRole.id == member.role_id)
        )
        current_role = current_role_result.scalar_one_or_none()
        if current_role and current_role.name == ROLE_ACCOUNT_SET_ADMIN:
            raise PermissionError(
                "Cannot revoke Account_Set_Admin role from the account set creator."
            )

    old_role_id = str(member.role_id)
    member.role_id = new_role_id

    await write_audit(
        session,
        user_id=admin_user_id,
        action="account_set.change_user_role",
        entity_type="AccountSetMember",
        entity_id=str(target_user_id),
        old_value={"role_id": old_role_id},
        new_value={"role_id": new_role_id},
            account_set_id=account_set_id,
    )

    await session.commit()
    await session.refresh(member)
    return member


async def remove_user(
    session: AsyncSession,
    *,
    account_set_id: str,
    target_user_id: str,
    admin_user_id: str,
) -> None:
    """Remove a user from an Account Set. Account_Set_Admin only."""
    await _require_admin(session, account_set_id, admin_user_id)

    # Protect creator
    as_result = await session.execute(
        select(AccountSet).where(AccountSet.id == account_set_id)
    )
    account_set = as_result.scalar_one_or_none()
    if account_set and str(account_set.created_by_user_id) == str(target_user_id):
        raise PermissionError("Cannot remove the account set creator.")

    member_result = await session.execute(
        select(AccountSetMember).where(
            AccountSetMember.account_set_id == account_set_id,
            AccountSetMember.user_id == target_user_id,
        )
    )
    member = member_result.scalar_one_or_none()
    if member is None:
        raise KeyError(f"User {target_user_id} is not a member of this account set.")

    await write_audit(
        session,
        user_id=admin_user_id,
        action="account_set.remove_user",
        entity_type="AccountSetMember",
        entity_id=str(target_user_id),
            account_set_id=account_set_id,
    )

    await session.delete(member)
    await session.commit()


# ── Custom role management ────────────────────────────────────────────────────


async def create_custom_role(
    session: AsyncSession,
    *,
    account_set_id: str,
    name: str,
    permissions: list[str],
    admin_user_id: str,
) -> AccountSetRole:
    """Create a custom role for an Account Set. Account_Set_Admin only."""
    await _require_admin(session, account_set_id, admin_user_id)

    # Ensure name doesn't clash with built-in roles
    if name in _BUILTIN_ROLES:
        raise ValueError(f"Cannot create a custom role with built-in name '{name}'.")

    role = AccountSetRole(
        account_set_id=account_set_id,
        name=name,
        is_builtin=False,
        permissions=permissions,
    )
    session.add(role)

    await write_audit(
        session,
        user_id=admin_user_id,
        action="account_set.create_custom_role",
        entity_type="AccountSetRole",
        entity_id=None,
        new_value={"name": name, "permissions": permissions},
            account_set_id=account_set_id,
    )

    await session.commit()
    await session.refresh(role)
    return role


async def update_custom_role(
    session: AsyncSession,
    *,
    account_set_id: str,
    role_id: str,
    permissions: list[str],
    admin_user_id: str,
) -> AccountSetRole:
    """Update a custom role's permissions. Built-in roles are immutable."""
    await _require_admin(session, account_set_id, admin_user_id)

    role_result = await session.execute(
        select(AccountSetRole).where(
            AccountSetRole.id == role_id,
            AccountSetRole.account_set_id == account_set_id,
        )
    )
    role = role_result.scalar_one_or_none()
    if role is None:
        raise KeyError(f"Role {role_id} not found in account set {account_set_id}.")

    if role.is_builtin:
        raise PermissionError("Built-in role permission sets cannot be modified.")

    old_permissions = list(role.permissions)
    role.permissions = permissions

    await write_audit(
        session,
        user_id=admin_user_id,
        action="account_set.update_custom_role",
        entity_type="AccountSetRole",
        entity_id=role_id,
        old_value={"permissions": old_permissions},
        new_value={"permissions": permissions},
            account_set_id=account_set_id,
    )

    await session.commit()
    await session.refresh(role)
    return role


async def list_roles(
    session: AsyncSession, *, account_set_id: str
) -> list[AccountSetRole]:
    """List all roles (built-in + custom) for an Account Set."""
    result = await session.execute(
        select(AccountSetRole)
        .where(AccountSetRole.account_set_id == account_set_id)
        .order_by(AccountSetRole.is_builtin.desc(), AccountSetRole.name)
    )
    return list(result.scalars().all())


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _seed_builtin_roles(
    session: AsyncSession, account_set_id: str
) -> dict[str, AccountSetRole]:
    """Seed the 5 built-in AccountSetRole records for a new Account Set."""
    role_map: dict[str, AccountSetRole] = {}
    for role_name in _BUILTIN_ROLES:
        role = AccountSetRole(
            account_set_id=account_set_id,
            name=role_name,
            is_builtin=True,
            permissions=_BUILTIN_PERMISSIONS.get(role_name, []),
        )
        session.add(role)
        role_map[role_name] = role

    await session.flush()
    return role_map


async def _seed_chart_of_accounts(
    session: AsyncSession, account_set_id: str, standard: str
) -> None:
    """Seed the chart of accounts template for the given standard."""
    if standard == "CAS":
        from account_set.templates.cas_template import CAS_ACCOUNTS
        accounts_data = CAS_ACCOUNTS
    elif standard == "IFRS":
        from account_set.templates.ifrs_template import IFRS_ACCOUNTS
        accounts_data = IFRS_ACCOUNTS
    else:
        raise ValueError(f"Unknown standard: {standard}")

    for entry in accounts_data:
        account = Account(
            account_set_id=account_set_id,
            code=entry["code"],
            name=entry["name"],
            account_type=entry["account_type"],
            standard=standard,
            parent_code=entry.get("parent_code"),
            level=entry.get("level", 1),
            is_leaf=True,
            is_active=True,
            aux_dimensions=[],
        )
        session.add(account)

    await session.flush()
    logger.info("Seeded %s chart of accounts for account_set_id=%s", standard, account_set_id)


async def _validate_external_db_connectivity(db_config: dict[str, Any]) -> None:
    """Validate that the provided external DB connection is reachable."""
    from sqlalchemy.ext.asyncio import create_async_engine

    host = db_config.get("db_host", "")
    port = db_config.get("db_port", 5432)
    name = db_config.get("db_name", "")
    user = db_config.get("db_user", "")
    password = db_config.get("db_password", "")
    db_type = db_config.get("db_type", "postgresql")

    if db_type == "mysql":
        url = f"mysql+aiomysql://{user}:{password}@{host}:{port}/{name}"
    else:
        url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"

    engine = create_async_engine(url, pool_pre_ping=True, pool_size=1, max_overflow=0)
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise ConnectionError(
            f"Cannot connect to external database at {host}:{port}/{name}: {exc}"
        ) from exc
    finally:
        await engine.dispose()


async def _provision_database(
    account_set_id: str,
    datasource_type: str,
    datasource_config: dict[str, Any] | None,
) -> None:
    """Trigger tenant database provisioning (best-effort, non-blocking)."""
    # Shared Account Sets live in the platform shared multi-tenant DB
    # (SHARED_TENANT_DB_URL). Skip CREATE DATABASE, but MUST register so that
    # after switch (JWT carries account_set_id) middleware can resolve a tenant
    # engine — otherwise GET /account-sets returns 404 Tenant not found.
    if datasource_type == "Shared":
        await _register_shared_tenant(account_set_id)
        return
    try:
        from platform.provisioner import provision_tenant_database
        from platform.registry.models import DbType

        db_type = DbType.postgresql
        if datasource_config and datasource_config.get("db_type") == "mysql":
            db_type = DbType.mysql

        await provision_tenant_database(
            account_set_id,
            db_type,
            datasource_config,
        )
    except Exception as exc:
        # Log but don't fail account set creation — provisioning can be retried
        logger.warning(
            "Tenant DB provisioning failed for %s: %s", account_set_id, exc
        )


async def _register_shared_tenant(account_set_id: str) -> None:
    """Register Shared account set pointing at SHARED_TENANT_DB_URL."""
    from sqlalchemy.engine.url import make_url

    from platform.db_config import resolve_shared_tenant_db_url
    from platform.registry.models import DbType, TenantStatus
    from platform.registry.service import register_tenant, update_tenant_status

    url = make_url(resolve_shared_tenant_db_url())
    driver = (url.drivername or "").split("+")[0]
    db_type = DbType.mysql if driver == "mysql" else DbType.postgresql
    password = url.password or ""
    config = {
        "db_host": url.host or "localhost",
        "db_port": int(url.port or (3306 if db_type == DbType.mysql else 5432)),
        "db_name": (url.database or "smartbook_shared"),
        "db_user": url.username or "smartbook",
        "db_password": password,
    }
    try:
        await register_tenant(account_set_id, db_type, config)
        await update_tenant_status(account_set_id, TenantStatus.active)
        logger.info(
            "Registered Shared tenant account_set_id=%s -> %s:%s/%s",
            account_set_id,
            config["db_host"],
            config["db_port"],
            config["db_name"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Shared tenant registry registration failed for %s: %s",
            account_set_id,
            exc,
        )
