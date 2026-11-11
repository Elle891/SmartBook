"""NLP Assistant API schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    account_set_id: str
    session_id: Optional[str] = None
    confirmed: bool = False
    params: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: str
    intent: str
    confidence: float
    model_used: str
    language: str
    response: str
