"""NLP Assistant FastAPI router (Task 29)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_current_user
from auth.rbac import PERM_LEDGER, require_permission
from nlp import service as nlp_svc
from platform.db_router import get_tenant_db
from schemas.nlp_api import ChatRequest, ChatResponse

router = APIRouter(prefix="/nlp", tags=["nlp"])

TenantDB = AsyncSession  # injected via Depends(get_tenant_db)


def _user_id(user: dict[str, Any]) -> str:
    return user.get("user_id") or user.get("sub", "")


def _role(user: dict[str, Any]) -> str:
    return user.get("role", "Viewer")


def _account_set_guard(user: dict[str, Any], account_set_id: str) -> str:
    jwt_account_set_id = user.get("account_set_id", "")
    if jwt_account_set_id and jwt_account_set_id != account_set_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_set_id does not match the active Account Set in your session.",
        )
    return account_set_id


@router.post("/chat", response_model=ChatResponse)
async def api_chat(
    body: ChatRequest,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_LEDGER)),
    db: TenantDB = Depends(get_tenant_db),
):
    aid = _account_set_guard(user, body.account_set_id)
    result = await nlp_svc.handle_chat(
        db,
        account_set_id=aid,
        user_id=_user_id(user),
        role=_role(user),
        message=body.message,
        session_id=body.session_id,
        confirmed=body.confirmed,
        params=body.params,
    )
    return ChatResponse(
        session_id=result["session_id"],
        intent=result["intent"],
        confidence=result["confidence"],
        model_used=result["model_used"],
        language=result["language"],
        response=result["response"],
    )


@router.delete("/sessions/{session_id}/context", status_code=status.HTTP_204_NO_CONTENT)
async def api_clear_context(
    session_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
    _perm: None = Depends(require_permission(PERM_LEDGER)),
):
    _ = user
    await nlp_svc.clear_context(str(session_id))
