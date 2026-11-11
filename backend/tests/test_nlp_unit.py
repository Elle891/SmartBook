"""
Unit tests for NLP Assistant (Task 29).
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest

os.environ["NLP_BACKEND"] = "stub"
os.environ["NLP_CONTEXT_BACKEND"] = "memory"

from auth.rbac import ROLE_VIEWER
from nlp import conversation_context, service as nlp_svc
from nlp.conversation_context import MAX_TURNS, clear_memory_store
from nlp.intent_classifier import classify_intent, detect_language
from nlp.langchain_pipeline import execute_action


@pytest.fixture(autouse=True)
def _reset_context():
    clear_memory_store()
    conversation_context.clear_memory_store()
    yield
    clear_memory_store()
    conversation_context.clear_memory_store()


class TestIntentClassifier:
    def test_detects_chinese(self):
        assert detect_language("我的余额") == "zh-CN"

    def test_classifies_balance_query(self):
        result = classify_intent("what is my cash balance")
        assert result.intent == "query_balance"


class TestConversationContext:
    @pytest.mark.asyncio
    async def test_sliding_window_max_ten_turns(self):
        sid = str(uuid.uuid4())
        for i in range(12):
            await conversation_context.append_turn(sid, role="user", content=f"msg-{i}")
        turns = await conversation_context.get_context(sid)
        assert len(turns) == MAX_TURNS
        assert turns[0]["content"] == "msg-2"

    @pytest.mark.asyncio
    async def test_clear_context(self):
        sid = str(uuid.uuid4())
        await conversation_context.append_turn(sid, role="user", content="hello")
        await conversation_context.clear_context(sid)
        assert await conversation_context.get_context(sid) == []


class TestChatService:
    @pytest.mark.asyncio
    async def test_handle_chat_query(self):
        from unittest.mock import MagicMock

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch.object(nlp_svc, "_get_or_create_session", AsyncMock()) as mock_session, \
             patch.object(nlp_svc, "_log_interaction", AsyncMock()), \
             patch("nlp.service.write_tenant_audit", AsyncMock()):
            session = MagicMock()
            session.id = uuid.uuid4()
            mock_session.return_value = session

            result = await nlp_svc.handle_chat(
                db,
                account_set_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
                role=ROLE_VIEWER,
                message="what is my cash balance",
            )

        assert result["intent"] == "query_balance"
        assert "response" in result


class TestActionConfirmation:
    @pytest.mark.asyncio
    async def test_action_requires_confirmation(self):
        from nlp.errors import ConfirmationRequiredError

        with pytest.raises(ConfirmationRequiredError):
            await execute_action(
                AsyncMock(),
                account_set_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
                role="Account_Set_Admin",
                intent="create_voucher",
                params={"amount": 5000},
                confirmed=False,
            )
