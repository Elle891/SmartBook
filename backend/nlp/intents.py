"""Intent definitions and RBAC mapping."""

from __future__ import annotations

from auth.rbac import (
    PERM_CASHIER,
    PERM_LEDGER,
    PERM_PERIOD_END,
    PERM_REPORTS,
    PERM_USER_MANAGEMENT,
    PERM_VOUCHERS,
    _BUILTIN_PERMISSIONS,
)

CATEGORY_QUERY = "query"
CATEGORY_ACTION = "action"
CATEGORY_GUIDANCE = "guidance"
CATEGORY_UNKNOWN = "unknown"

INTENT_QUERY_BALANCE = "query_balance"
INTENT_QUERY_LEDGER = "query_ledger"
INTENT_QUERY_VOUCHER = "query_voucher"
INTENT_QUERY_REPORT = "query_report"
INTENT_QUERY_FORECAST = "query_forecast"

INTENT_CREATE_VOUCHER = "create_voucher"
INTENT_SUBMIT_PAYMENT = "submit_payment"
INTENT_RUN_RECONCILIATION = "run_reconciliation"
INTENT_GENERATE_REPORT = "generate_report"
INTENT_CLOSE_PERIOD = "close_period"

INTENT_GUIDE_PERIOD_CLOSE = "guide_period_close"
INTENT_GUIDE_ASSET = "guide_asset_registration"
INTENT_GUIDE_PAYROLL = "guide_payroll"
INTENT_GUIDE_IFRS = "guide_ifrs_recognition"

INTENT_UNKNOWN = "unknown"

QUERY_INTENTS = {
    INTENT_QUERY_BALANCE,
    INTENT_QUERY_LEDGER,
    INTENT_QUERY_VOUCHER,
    INTENT_QUERY_REPORT,
    INTENT_QUERY_FORECAST,
}

ACTION_INTENTS = {
    INTENT_CREATE_VOUCHER,
    INTENT_SUBMIT_PAYMENT,
    INTENT_RUN_RECONCILIATION,
    INTENT_GENERATE_REPORT,
    INTENT_CLOSE_PERIOD,
}

GUIDANCE_INTENTS = {
    INTENT_GUIDE_PERIOD_CLOSE,
    INTENT_GUIDE_ASSET,
    INTENT_GUIDE_PAYROLL,
    INTENT_GUIDE_IFRS,
}

INTENT_PERMISSION: dict[str, str | None] = {
    INTENT_CREATE_VOUCHER: PERM_VOUCHERS,
    INTENT_SUBMIT_PAYMENT: PERM_CASHIER,
    INTENT_RUN_RECONCILIATION: PERM_CASHIER,
    INTENT_GENERATE_REPORT: PERM_REPORTS,
    INTENT_CLOSE_PERIOD: PERM_PERIOD_END,
    INTENT_QUERY_BALANCE: PERM_LEDGER,
    INTENT_QUERY_LEDGER: PERM_LEDGER,
    INTENT_QUERY_VOUCHER: PERM_VOUCHERS,
    INTENT_QUERY_REPORT: PERM_REPORTS,
    INTENT_QUERY_FORECAST: PERM_REPORTS,
}


def intent_category(intent: str) -> str:
    if intent in QUERY_INTENTS:
        return CATEGORY_QUERY
    if intent in ACTION_INTENTS:
        return CATEGORY_ACTION
    if intent in GUIDANCE_INTENTS:
        return CATEGORY_GUIDANCE
    return CATEGORY_UNKNOWN


def role_has_permission(role: str, permission: str) -> bool:
    return permission in _BUILTIN_PERMISSIONS.get(role, [])


def action_allowed(role: str, intent: str) -> bool:
    permission = INTENT_PERMISSION.get(intent)
    if permission is None:
        return intent not in ACTION_INTENTS
    return role_has_permission(role, permission)
