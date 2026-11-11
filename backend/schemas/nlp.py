"""
Pydantic v2 schemas for ConversationSession, ConversationTurn, NLPInteractionLog.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── ConversationSession ───────────────────────────────────────────────────────

class ConversationSessionCreate(BaseModel):
    account_set_id: uuid.UUID


class ConversationSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    account_set_id: uuid.UUID
    started_at: datetime
    last_active_at: datetime


# ── ConversationTurn ──────────────────────────────────────────────────────────

class ConversationTurnCreate(BaseModel):
    role: str = Field(description="user or assistant")
    content: str = Field(min_length=1)
    intent: Optional[str] = Field(default=None, max_length=128)


class ConversationTurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    intent: Optional[str]
    created_at: datetime


# ── NLPInteractionLog ─────────────────────────────────────────────────────────

class NLPInteractionLogCreate(BaseModel):
    session_id: uuid.UUID
    account_set_id: uuid.UUID
    intent: str = Field(min_length=1, max_length=128)
    action_taken: str = Field(min_length=1, max_length=256)
    success: bool


class NLPInteractionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    user_id: uuid.UUID
    account_set_id: uuid.UUID
    intent: str
    action_taken: str
    success: bool
    created_at: datetime
