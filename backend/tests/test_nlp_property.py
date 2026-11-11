"""
Property tests for NLP Assistant (Task 29.1–29.4).

# Feature: smart-accounting-software, Properties 17–20
**Validates: Requirements 24.3, 24.9, 24.10, 24.12**
"""

from __future__ import annotations

import os

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

os.environ.setdefault("NLP_BACKEND", "stub")
os.environ.setdefault("NLP_CONTEXT_BACKEND", "memory")

from auth.rbac import ROLE_ACCOUNT_SET_ADMIN, ROLE_VIEWER
from nlp.errors import UnauthorizedActionError
from nlp.intent_classifier import (
    MODEL_RULE_BASED,
    canonical_intent_for_paraphrase,
    classify_intent,
)
from nlp.intents import INTENT_CLOSE_PERIOD, INTENT_QUERY_BALANCE, action_allowed
from nlp.langchain_pipeline import execute_action
from nlp.sanitizer import contains_sensitive_data, sanitize_response

_PARAPHRASE_PAIRS = [
    ("what is my cash balance", "show me the cash balance"),
    ("what is my cash balance", "我的现金余额是多少"),
    ("how do i close the period", "如何关账"),
]

_SENSITIVE_SAMPLES = [
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature",
    "api_key=sk-live-abcdef123456",
    "postgresql://user:secret@db.internal:5432/tenant",
    "SELECT * FROM users WHERE password='x'",
    "/account-sets/00000000-0000-0000-0000-000000000001/vouchers",
]


class TestProperty17IntentConsistency:
    @given(pair=st.sampled_from(_PARAPHRASE_PAIRS))
    @settings(max_examples=10)
    def test_paraphrases_share_canonical_intent(self, pair: tuple[str, str]) -> None:
        a, b = pair
        assert canonical_intent_for_paraphrase(a) == canonical_intent_for_paraphrase(b)

    def test_balance_paraphrases(self):
        assert canonical_intent_for_paraphrase("what is my cash balance") == INTENT_QUERY_BALANCE
        assert canonical_intent_for_paraphrase("查看现金余额") == INTENT_QUERY_BALANCE


class TestProperty18RbacEnforcement:
    @pytest.mark.asyncio
    async def test_viewer_cannot_close_period(self):
        db = None
        with pytest.raises(UnauthorizedActionError):
            await execute_action(
                db,  # type: ignore[arg-type]
                account_set_id=str("00000000-0000-0000-0000-000000000001"),
                user_id=str("00000000-0000-0000-0000-000000000002"),
                role=ROLE_VIEWER,
                intent=INTENT_CLOSE_PERIOD,
                params={"period_code": "202506"},
                confirmed=True,
            )

    def test_admin_may_close_period(self):
        assert action_allowed(ROLE_ACCOUNT_SET_ADMIN, INTENT_CLOSE_PERIOD) is True

    def test_viewer_denied_close_period(self):
        assert action_allowed(ROLE_VIEWER, INTENT_CLOSE_PERIOD) is False


class TestProperty19NoSensitiveLeakage:
    @given(sample=st.sampled_from(_SENSITIVE_SAMPLES))
    @settings(max_examples=10)
    def test_sanitizer_redacts_sensitive_patterns(self, sample: str) -> None:
        cleaned = sanitize_response(f"Here is data: {sample}")
        assert not contains_sensitive_data(cleaned)

    def test_clean_response_unchanged(self):
        text = "Your cash balance is 12,500 CNY."
        assert sanitize_response(text) == text


class TestProperty20FallbackClassifier:
    def test_low_confidence_uses_rule_based_fallback(self):
        result = classify_intent("something ambiguous xyz", force_low_confidence=True)
        assert result.model_used == MODEL_RULE_BASED

    def test_clear_balance_query_uses_embedding_or_rules(self):
        result = classify_intent("what is my cash balance")
        assert result.intent == INTENT_QUERY_BALANCE
        assert result.confidence >= 0.7
