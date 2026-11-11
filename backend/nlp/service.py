"""
NLP Assistant orchestration service (Task 29).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nlp import conversation_context, langchain_pipeline
from nlp.errors import ConfirmationRequiredError, NLPError, UnauthorizedActionError
from nlp.intent_classifier import classify_intent
from nlp.intents import action_allowed
from nlp.sanitizer import sanitize_response
from models.nlp import ConversationSession, ConversationTurn, NLPInteractionLog
from voucher.service import write_tenant_audit


async def _get_or_create_session(
    db: AsyncSession,
    *,
    session_id: str | None,
    user_id: str,
    account_set_id: str,
) -> ConversationSession:
    if session_id:
        result = await db.execute(
            select(ConversationSession).where(
                ConversationSession.id == session_id,
                ConversationSession.user_id == uuid.UUID(user_id),
                ConversationSession.account_set_id == uuid.UUID(account_set_id),
            )
        )
        session = result.scalar_one_or_none()
        if session is not None:
            session.last_active_at = datetime.now(timezone.utc)
            return session

    session = ConversationSession(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        account_set_id=uuid.UUID(account_set_id),
    )
    db.add(session)
    await db.flush()
    return session


async def _log_interaction(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    user_id: str,
    account_set_id: str,
    intent: str,
    action_taken: str,
    success: bool,
    user_message: str,
    response_text: str,
    confidence: float,
    model_used: str,
    rbac_check_passed: bool | None,
    language: str,
) -> None:
    db.add(
        NLPInteractionLog(
            id=uuid.uuid4(),
            session_id=session_id,
            user_id=uuid.UUID(user_id),
            account_set_id=uuid.UUID(account_set_id),
            intent=intent,
            action_taken=action_taken,
            success=success,
            user_message=user_message,
            response_text=response_text,
            confidence=confidence,
            model_used=model_used,
            rbac_check_passed=rbac_check_passed,
            language=language,
        )
    )
    await write_tenant_audit(
        db,
        account_set_id=account_set_id,
        user_id=user_id,
        action="nlp.interaction",
        entity_type="ConversationSession",
        entity_id=str(session_id),
        old_value=None,
        new_value={
            "intent": intent,
            "success": success,
            "model_used": model_used,
            "rbac_check_passed": rbac_check_passed,
        },
    )


def _http_error(exc: NLPError) -> HTTPException:
    code = status.HTTP_422_UNPROCESSABLE_ENTITY
    if isinstance(exc, UnauthorizedActionError):
        code = status.HTTP_403_FORBIDDEN
    return HTTPException(status_code=code, detail=exc.to_dict())


async def handle_chat(
    db: AsyncSession,
    *,
    account_set_id: str,
    user_id: str,
    role: str,
    message: str,
    session_id: str | None = None,
    confirmed: bool = False,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_message = message.strip()
    if not clean_message:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message is required.")

    session = await _get_or_create_session(
        db, session_id=session_id, user_id=user_id, account_set_id=account_set_id
    )
    sid = str(session.id)

    await conversation_context.append_turn(sid, role="user", content=clean_message)
    classification = classify_intent(clean_message)
    rbac_passed: bool | None = None
    success = True
    action_taken = "classify_intent"

    try:
        from nlp.intents import ACTION_INTENTS

        if classification.intent in ACTION_INTENTS:
            rbac_passed = action_allowed(role, classification.intent)

        result = await langchain_pipeline.route_intent(
            db,
            account_set_id=account_set_id,
            user_id=user_id,
            role=role,
            intent=classification.intent,
            message=clean_message,
            params=params or {},
            language=classification.language,
            confirmed=confirmed,
        )
        response_text = sanitize_response(str(result.get("message", "")))
        action_taken = classification.intent
    except UnauthorizedActionError as exc:
        success = False
        rbac_passed = False
        response_text = sanitize_response(exc.message)
        await _log_interaction(
            db,
            session_id=session.id,
            user_id=user_id,
            account_set_id=account_set_id,
            intent=classification.intent,
            action_taken="rbac_denied",
            success=False,
            user_message=clean_message,
            response_text=response_text,
            confidence=classification.confidence,
            model_used=classification.model_used,
            rbac_check_passed=False,
            language=classification.language,
        )
        raise _http_error(exc) from exc
    except ConfirmationRequiredError as exc:
        success = True
        rbac_passed = action_allowed(role, classification.intent)
        response_text = sanitize_response(exc.message)
        result = exc.to_dict()
        await conversation_context.append_turn(
            sid, role="assistant", content=response_text, intent=classification.intent
        )
        await _log_interaction(
            db,
            session_id=session.id,
            user_id=user_id,
            account_set_id=account_set_id,
            intent=classification.intent,
            action_taken="confirmation_required",
            success=True,
            user_message=clean_message,
            response_text=response_text,
            confidence=classification.confidence,
            model_used=classification.model_used,
            rbac_check_passed=rbac_passed,
            language=classification.language,
        )
        return {
            "session_id": sid,
            "intent": classification.intent,
            "confidence": classification.confidence,
            "model_used": classification.model_used,
            "language": classification.language,
            "response": response_text,
            **result,
        }
    except NLPError as exc:
        success = False
        raise _http_error(exc) from exc

    await conversation_context.append_turn(
        sid, role="assistant", content=response_text, intent=classification.intent
    )
    db.add(
        ConversationTurn(
            id=uuid.uuid4(),
            session_id=session.id,
            role="user",
            content=clean_message,
            intent=classification.intent,
        )
    )
    db.add(
        ConversationTurn(
            id=uuid.uuid4(),
            session_id=session.id,
            role="assistant",
            content=response_text,
            intent=classification.intent,
        )
    )
    await _log_interaction(
        db,
        session_id=session.id,
        user_id=user_id,
        account_set_id=account_set_id,
        intent=classification.intent,
        action_taken=action_taken,
        success=success,
        user_message=clean_message,
        response_text=response_text,
        confidence=classification.confidence,
        model_used=classification.model_used,
        rbac_check_passed=rbac_passed,
        language=classification.language,
    )

    payload = {
        "session_id": sid,
        "intent": classification.intent,
        "confidence": classification.confidence,
        "model_used": classification.model_used,
        "language": classification.language,
        "response": response_text,
    }
    if isinstance(result, dict):
        payload.update({k: v for k, v in result.items() if k != "message"})
    return payload


async def get_conversation_context(session_id: str) -> list[dict[str, str]]:
    return await conversation_context.get_context(session_id)


async def clear_context(session_id: str) -> None:
    await conversation_context.clear_context(session_id)
