"""
LangChain-style tool routing pipeline (Task 29).

Uses explicit dispatch rather than requiring LangChain at runtime in tests.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from nlp.deepseek_client import DeepSeekUnavailableError, generate_guidance
from nlp.errors import ConfirmationRequiredError, UnauthorizedActionError
from nlp.intents import (
    CATEGORY_ACTION,
    CATEGORY_GUIDANCE,
    CATEGORY_QUERY,
    INTENT_GUIDE_PERIOD_CLOSE,
    action_allowed,
    intent_category,
)
from nlp.sanitizer import sanitize_response


async def execute_query(
    db: AsyncSession,
    *,
    account_set_id: str,
    intent: str,
    params: dict[str, Any],
    role: str,
) -> dict[str, Any]:
    """Read-only query handlers."""
    _ = role
    if intent == "query_balance":
        return {
            "message": sanitize_response(
                "Your cash and bank accounts show a combined balance based on the latest ledger data."
            ),
            "data": {"account_set_id": account_set_id, "source": "ledger"},
        }
    if intent == "query_forecast":
        return {
            "message": sanitize_response(
                "Cash flow forecast is available from the Forecast page for horizons up to 12 months."
            ),
            "data": {},
        }
    if intent == "query_ledger":
        return {
            "message": sanitize_response("Ledger entries can be viewed in the Ledger module for the selected period."),
            "data": params,
        }
    return {
        "message": sanitize_response("I retrieved the requested information from your account set."),
        "data": params,
    }


async def execute_action(
    db: AsyncSession,
    *,
    account_set_id: str,
    user_id: str,
    role: str,
    intent: str,
    params: dict[str, Any],
    confirmed: bool,
) -> dict[str, Any]:
    """Write actions — RBAC first, confirmation required before execution."""
    if intent_category(intent) != CATEGORY_ACTION:
        raise UnauthorizedActionError("Intent is not an action.")

    if not action_allowed(role, intent):
        raise UnauthorizedActionError(
            f"Role '{role}' is not authorized to perform '{intent}'.",
            details={"intent": intent, "role": role, "rbac_check_passed": False},
        )

    if not confirmed:
        summary = _action_summary(intent, params)
        raise ConfirmationRequiredError(
            "Please confirm this action before execution.",
            details={
                "intent": intent,
                "confirmation_required": True,
                "summary": summary,
                "params": params,
            },
        )

    # Simulated execution — no direct API call without authorization + confirmation
    return {
        "message": sanitize_response(f"Action '{intent}' has been queued for processing."),
        "executed": True,
        "intent": intent,
        "account_set_id": account_set_id,
        "user_id": user_id,
    }


def _action_summary(intent: str, params: dict[str, Any]) -> str:
    amount = params.get("amount", "")
    if intent == "create_voucher":
        return f"Create voucher for amount {amount}".strip()
    if intent == "submit_payment":
        return f"Submit payment for amount {amount}".strip()
    if intent == "close_period":
        return f"Close period {params.get('period_code', '')}".strip()
    return f"Execute {intent}"


async def generate_guidance_response(
    *,
    intent: str,
    message: str,
    language: str,
    accounting_standard: str = "CAS",
) -> dict[str, Any]:
    topic_map = {
        INTENT_GUIDE_PERIOD_CLOSE: "period_close",
    }
    topic = topic_map.get(intent, message)
    try:
        text = await generate_guidance(
            topic=topic, language=language, accounting_standard=accounting_standard
        )
        limited = False
    except DeepSeekUnavailableError:
        text = _fallback_guidance(
            topic=topic, language=language, accounting_standard=accounting_standard
        )
        limited = True
    return {
        "message": sanitize_response(text),
        "ai_limited": limited,
        "category": CATEGORY_GUIDANCE,
    }


async def route_intent(
    db: AsyncSession,
    *,
    account_set_id: str,
    user_id: str,
    role: str,
    intent: str,
    message: str,
    params: dict[str, Any],
    language: str,
    confirmed: bool,
) -> dict[str, Any]:
    category = intent_category(intent)
    if category == CATEGORY_QUERY:
        return await execute_query(
            db, account_set_id=account_set_id, intent=intent, params=params, role=role
        )
    if category == CATEGORY_ACTION:
        return await execute_action(
            db,
            account_set_id=account_set_id,
            user_id=user_id,
            role=role,
            intent=intent,
            params=params,
            confirmed=confirmed,
        )
    if category == CATEGORY_GUIDANCE:
        return await generate_guidance_response(
            intent=intent, message=message, language=language
        )
    return {
        "message": sanitize_response(
            "Could you clarify what you would like to do? "
            "I can help with balances, reports, vouchers, or step-by-step guidance."
        ),
        "clarification_required": True,
    }
