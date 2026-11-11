"""
Chart of Accounts service — account tree management.

Supports CAS and IFRS numbering schemes with up to 4 levels of hierarchy.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.account import Account

logger = logging.getLogger(__name__)

# ── Allowed auxiliary dimensions ──────────────────────────────────────────────

VALID_AUX_DIMENSIONS = {"department", "project", "customer", "supplier", "employee"}

# ── CAS numbering ranges ──────────────────────────────────────────────────────
# 1xxx = Asset, 2xxx = Liability, 3xxx = Equity, 4xxx-5xxx = Revenue, 6xxx = Expense

_CAS_TYPE_RANGES: dict[str, tuple[int, int]] = {
    "Asset":     (1000, 1999),
    "Liability": (2000, 2999),
    "Equity":    (3000, 3999),
    "Revenue":   (4000, 5999),
    "Expense":   (6000, 6999),
}

VALID_ACCOUNT_TYPES = {"Asset", "Liability", "Equity", "Revenue", "Expense"}

# ── CAS standard template ─────────────────────────────────────────────────────

_CAS_TEMPLATE: list[dict[str, Any]] = [
    {"code": "1001", "name": "库存现金", "account_type": "Asset", "parent_code": None},
    {"code": "1002", "name": "银行存款", "account_type": "Asset", "parent_code": None},
    {"code": "1122", "name": "应收账款", "account_type": "Asset", "parent_code": None},
    {"code": "1405", "name": "库存商品", "account_type": "Asset", "parent_code": None},
    {"code": "1601", "name": "固定资产", "account_type": "Asset", "parent_code": None},
    {"code": "2001", "name": "短期借款", "account_type": "Liability", "parent_code": None},
    {"code": "2202", "name": "应付账款", "account_type": "Liability", "parent_code": None},
    {"code": "2221", "name": "应交税费", "account_type": "Liability", "parent_code": None},
    {"code": "3001", "name": "实收资本", "account_type": "Equity", "parent_code": None},
    {"code": "3002", "name": "资本公积", "account_type": "Equity", "parent_code": None},
    {"code": "3101", "name": "盈余公积", "account_type": "Equity", "parent_code": None},
    {"code": "3131", "name": "本年利润", "account_type": "Equity", "parent_code": None},
    {"code": "3141", "name": "利润分配", "account_type": "Equity", "parent_code": None},
    {"code": "5001", "name": "主营业务收入", "account_type": "Revenue", "parent_code": None},
    {"code": "5051", "name": "其他业务收入", "account_type": "Revenue", "parent_code": None},
    {"code": "6001", "name": "主营业务成本", "account_type": "Expense", "parent_code": None},
    {"code": "6051", "name": "其他业务成本", "account_type": "Expense", "parent_code": None},
    {"code": "6601", "name": "销售费用", "account_type": "Expense", "parent_code": None},
    {"code": "6602", "name": "管理费用", "account_type": "Expense", "parent_code": None},
    {"code": "6603", "name": "财务费用", "account_type": "Expense", "parent_code": None},
]

# ── IFRS standard template ────────────────────────────────────────────────────

_IFRS_TEMPLATE: list[dict[str, Any]] = [
    {"code": "1100", "name": "Cash and Cash Equivalents", "account_type": "Asset", "parent_code": None},
    {"code": "1200", "name": "Trade Receivables", "account_type": "Asset", "parent_code": None},
    {"code": "1300", "name": "Inventories", "account_type": "Asset", "parent_code": None},
    {"code": "1500", "name": "Property, Plant and Equipment", "account_type": "Asset", "parent_code": None},
    {"code": "1600", "name": "Right-of-Use Assets", "account_type": "Asset", "parent_code": None},
    {"code": "2100", "name": "Trade Payables", "account_type": "Liability", "parent_code": None},
    {"code": "2200", "name": "Lease Liabilities", "account_type": "Liability", "parent_code": None},
    {"code": "2300", "name": "Tax Liabilities", "account_type": "Liability", "parent_code": None},
    {"code": "3100", "name": "Share Capital", "account_type": "Equity", "parent_code": None},
    {"code": "3200", "name": "Retained Earnings", "account_type": "Equity", "parent_code": None},
    {"code": "3300", "name": "Other Comprehensive Income", "account_type": "Equity", "parent_code": None},
    {"code": "4100", "name": "Revenue", "account_type": "Revenue", "parent_code": None},
    {"code": "4200", "name": "Other Income", "account_type": "Revenue", "parent_code": None},
    {"code": "5100", "name": "Cost of Sales", "account_type": "Expense", "parent_code": None},
    {"code": "5200", "name": "Distribution Costs", "account_type": "Expense", "parent_code": None},
    {"code": "5300", "name": "Administrative Expenses", "account_type": "Expense", "parent_code": None},
    {"code": "5400", "name": "Finance Costs", "account_type": "Expense", "parent_code": None},
    {"code": "5500", "name": "Income Tax Expense", "account_type": "Expense", "parent_code": None},
]


# ── Code validation ───────────────────────────────────────────────────────────


def validate_code(standard: str, code: str, account_type: str) -> bool:
    """Validate account code against the standard's numbering scheme.

    CAS: enforces numeric ranges per account type.
    IFRS: flexible — only requires the code to be non-empty alphanumeric.
    """
    if not code or not code.strip():
        return False

    if standard == "CAS":
        if not code.isdigit():
            return False
        numeric = int(code)
        allowed = _CAS_TYPE_RANGES.get(account_type)
        if allowed is None:
            return False
        lo, hi = allowed
        return lo <= numeric <= hi

    if standard == "IFRS":
        # IFRS uses a flexible scheme — code must be non-empty alphanumeric
        return code.replace("-", "").replace(".", "").isalnum()

    return False


# ── Account tree helpers ──────────────────────────────────────────────────────


def _build_tree(accounts: list[Account]) -> list[dict]:
    """Build a nested tree from a flat list of Account rows."""
    by_code: dict[str, dict] = {}
    for acc in accounts:
        by_code[acc.code] = {
            "id": str(acc.id),
            "account_set_id": str(acc.account_set_id),
            "code": acc.code,
            "name": acc.name,
            "account_type": acc.account_type,
            "standard": acc.standard,
            "parent_code": acc.parent_code,
            "level": acc.level,
            "is_leaf": acc.is_leaf,
            "is_active": acc.is_active,
            "aux_dimensions": acc.aux_dimensions or [],
            "children": [],
        }

    roots: list[dict] = []
    for acc in accounts:
        node = by_code[acc.code]
        if acc.parent_code and acc.parent_code in by_code:
            by_code[acc.parent_code]["children"].append(node)
        else:
            roots.append(node)

    return roots


# ── Service functions ─────────────────────────────────────────────────────────


async def get_account_tree(account_set_id: str, db: AsyncSession) -> list[dict]:
    """Return the full account tree for an Account Set."""
    result = await db.execute(
        select(Account)
        .where(Account.account_set_id == account_set_id, Account.is_active == True)  # noqa: E712
        .order_by(Account.code)
    )
    accounts = list(result.scalars().all())
    return _build_tree(accounts)


async def create_account(
    account_set_id: str,
    code: str,
    name: str,
    account_type: str,
    standard: str,
    parent_code: str | None,
    db: AsyncSession,
) -> Account:
    """Create a new account in the Chart of Accounts.

    Validates:
    - account_type is one of the five valid types
    - code is unique within the Account Set
    - code conforms to the standard's numbering scheme
    - hierarchy depth does not exceed 4 levels
    - parent account exists (if parent_code provided)
    """
    if account_type not in VALID_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid account_type '{account_type}'. Must be one of: {sorted(VALID_ACCOUNT_TYPES)}",
        )

    if not validate_code(standard, code, account_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Account code '{code}' does not conform to {standard} numbering scheme "
                f"for account type '{account_type}'."
            ),
        )

    # Uniqueness check
    existing = await db.execute(
        select(Account).where(
            Account.account_set_id == account_set_id,
            Account.code == code,
            Account.is_active == True,  # noqa: E712
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account code '{code}' already exists in this Account Set.",
        )

    level = 1
    if parent_code:
        parent_result = await db.execute(
            select(Account).where(
                Account.account_set_id == account_set_id,
                Account.code == parent_code,
                Account.is_active == True,  # noqa: E712
            )
        )
        parent = parent_result.scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent account '{parent_code}' not found.",
            )
        level = parent.level + 1
        if level > 4:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Maximum account hierarchy depth is 4 levels.",
            )
        # Mark parent as non-leaf
        parent.is_leaf = False

    account = Account(
        account_set_id=account_set_id,
        code=code,
        name=name,
        account_type=account_type,
        standard=standard,
        parent_code=parent_code,
        level=level,
        is_leaf=True,
        is_active=True,
        aux_dimensions=[],
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    logger.info("Created account %s in account_set=%s", code, account_set_id)
    return account


async def delete_account(
    account_set_id: str, code: str, db: AsyncSession
) -> None:
    """Soft-delete an account.

    Rejects deletion if:
    - account does not exist
    - voucher entries reference this account (stub check — full check in task 9)
    - account has active children
    """
    result = await db.execute(
        select(Account).where(
            Account.account_set_id == account_set_id,
            Account.code == code,
            Account.is_active == True,  # noqa: E712
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account '{code}' not found.",
        )

    # Check for active children
    children_result = await db.execute(
        select(Account).where(
            Account.account_set_id == account_set_id,
            Account.parent_code == code,
            Account.is_active == True,  # noqa: E712
        )
    )
    if children_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete account '{code}': it has active child accounts.",
        )

    # Voucher entry check — deferred to task 9 when VoucherEntry model exists.
    # TODO (task 9): query VoucherEntry where account_code == code and raise 409 if any exist.
    _check_voucher_entries_stub(code)

    account.is_active = False
    # If parent exists, re-evaluate its is_leaf status
    if account.parent_code:
        siblings_result = await db.execute(
            select(Account).where(
                Account.account_set_id == account_set_id,
                Account.parent_code == account.parent_code,
                Account.is_active == True,  # noqa: E712
                Account.code != code,
            )
        )
        if not siblings_result.scalar_one_or_none():
            parent_result = await db.execute(
                select(Account).where(
                    Account.account_set_id == account_set_id,
                    Account.code == account.parent_code,
                )
            )
            parent = parent_result.scalar_one_or_none()
            if parent:
                parent.is_leaf = True

    await db.commit()
    logger.info("Deleted account %s from account_set=%s", code, account_set_id)


def _check_voucher_entries_stub(code: str) -> None:
    """Placeholder for voucher entry existence check (implemented in task 9)."""
    pass


async def enable_aux_dimension(
    account_set_id: str,
    code: str,
    dimensions: list[str],
    db: AsyncSession,
) -> Account:
    """Enable auxiliary dimensions on a leaf account.

    Only leaf accounts may have aux dimensions.
    Dimensions must be from the allowed set.
    """
    result = await db.execute(
        select(Account).where(
            Account.account_set_id == account_set_id,
            Account.code == code,
            Account.is_active == True,  # noqa: E712
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account '{code}' not found.",
        )

    if not account.is_leaf:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Auxiliary dimensions can only be enabled on leaf accounts. '{code}' has children.",
        )

    invalid = set(dimensions) - VALID_AUX_DIMENSIONS
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid dimensions: {sorted(invalid)}. Allowed: {sorted(VALID_AUX_DIMENSIONS)}",
        )

    account.aux_dimensions = list(set(dimensions))
    await db.commit()
    await db.refresh(account)
    logger.info("Updated aux_dimensions on account %s: %s", code, account.aux_dimensions)
    return account


def get_standard_template(standard: str) -> list[dict[str, Any]]:
    """Return the default chart of accounts template for a standard."""
    if standard == "CAS":
        return _CAS_TEMPLATE
    if standard == "IFRS":
        return _IFRS_TEMPLATE
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Unknown standard '{standard}'. Must be 'CAS' or 'IFRS'.",
    )
