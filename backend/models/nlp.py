"""
ConversationSession, ConversationTurn, NLPInteractionLog SQLAlchemy async models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, GUID, JsonType


class ConversationSession(Base):
    """A NLP conversation session between a user and the assistant."""

    __tablename__ = "conversation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), nullable=False, index=True
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<ConversationSession id={self.id} user={self.user_id}>"


class ConversationTurn(Base):
    """A single turn (message) within a ConversationSession."""

    __tablename__ = "conversation_turns"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("conversation_sessions.id"), nullable=False, index=True
    )
    # user or assistant
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<ConversationTurn id={self.id} role={self.role}>"


class NLPInteractionLog(Base):
    """Audit log for every NLP interaction."""

    __tablename__ = "nlp_interaction_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("conversation_sessions.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), nullable=False, index=True
    )
    account_set_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("account_sets.id"), nullable=False, index=True
    )
    intent: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action_taken: Mapped[str] = mapped_column(String(256), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rbac_check_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<NLPInteractionLog id={self.id} intent={self.intent}>"
