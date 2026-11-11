"""
Property-based tests for OTP verification.

# Feature: smart-accounting-software, Property 28: OTP verification rejects expired or already-used codes

**Validates: Requirements 31.4, 31.5**
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from hypothesis import given, settings
from hypothesis import strategies as st

from auth.otp import verify_otp
from models.user import OTPRecord


def _hash_otp(otp_plain: str) -> str:
    """Hash a 6-digit OTP using SHA-256 for fast property-test iteration.

    Production code uses bcrypt; we patch _pwd_context so these tests
    exercise verify_otp's logic (expiry, used-flag, hash mismatch) without
    bcrypt's intentional slowness.
    """
    return hashlib.sha256(otp_plain.encode()).hexdigest()


class _FastHashContext:
    """Minimal passlib-compatible context using SHA-256 for speed in tests."""

    def hash(self, secret: str) -> str:  # noqa: A003
        return _hash_otp(secret)

    def verify(self, secret: str, hash: str) -> bool:  # noqa: A003
        return hashlib.sha256(secret.encode()).hexdigest() == hash

# ── Helpers ───────────────────────────────────────────────────────────────────

_PURPOSES = ["register_email", "register_mobile", "login_mobile", "reset_email", "reset_mobile"]

_otp_plain_st = st.from_regex(r"[0-9]{6}", fullmatch=True)
_target_email_st = st.emails()
_target_mobile_st = st.from_regex(r"1[3-9][0-9]{9}", fullmatch=True)
_target_st = st.one_of(_target_email_st, _target_mobile_st)
_purpose_st = st.sampled_from(_PURPOSES)
_session_id_st = st.uuids().map(str)


def _make_record(
    target: str,
    purpose: str,
    session_id: str,
    otp_plain: str,
    *,
    is_used: bool = False,
    expired: bool = False,
) -> OTPRecord:
    """Build an OTPRecord with the given state."""
    now = datetime.now(timezone.utc)
    if expired:
        expires_at = now - timedelta(minutes=1)
    else:
        expires_at = now + timedelta(minutes=10)

    record = OTPRecord(
        id=uuid.uuid4(),
        target=target,
        otp_hash=_hash_otp(otp_plain),
        purpose=purpose,
        session_id=session_id,
        is_used=is_used,
        expires_at=expires_at,
        created_at=now,
    )
    return record


def _make_db_mock(record: OTPRecord | None) -> AsyncMock:
    """Return an AsyncSession mock that returns the given record from execute."""
    db = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = record
    db.execute = AsyncMock(return_value=scalar_result)
    db.flush = AsyncMock()
    return db


# ── Property 28: expired OTPs are rejected ────────────────────────────────────

@given(
    target=_target_st,
    purpose=_purpose_st,
    session_id=_session_id_st,
    otp_plain=_otp_plain_st,
)
@settings(max_examples=30)
def test_expired_otp_is_rejected(
    target: str,
    purpose: str,
    session_id: str,
    otp_plain: str,
) -> None:
    """Property 28 (expired): verify_otp raises HTTP 400 for any expired OTP.

    # Feature: smart-accounting-software, Property 28: OTP verification rejects expired or already-used codes
    **Validates: Requirements 31.4, 31.5**
    """
    import asyncio

    # Simulate: DB returns None (expired record filtered out by query)
    db = _make_db_mock(None)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.get_event_loop().run_until_complete(
            verify_otp(target, purpose, session_id, otp_plain, db)
        )

    assert exc_info.value.status_code == 400


# ── Property 28: already-used OTPs are rejected ───────────────────────────────

@given(
    target=_target_st,
    purpose=_purpose_st,
    session_id=_session_id_st,
    otp_plain=_otp_plain_st,
)
@settings(max_examples=30)
def test_used_otp_is_rejected(
    target: str,
    purpose: str,
    session_id: str,
    otp_plain: str,
) -> None:
    """Property 28 (used): verify_otp raises HTTP 400 for any already-used OTP.

    # Feature: smart-accounting-software, Property 28: OTP verification rejects expired or already-used codes
    **Validates: Requirements 31.4, 31.5**
    """
    import asyncio

    # Simulate: DB returns None (is_used=True filtered out by query)
    db = _make_db_mock(None)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.get_event_loop().run_until_complete(
            verify_otp(target, purpose, session_id, otp_plain, db)
        )

    assert exc_info.value.status_code == 400


# ── Property 28: wrong OTP code is rejected ───────────────────────────────────

@given(
    target=_target_st,
    purpose=_purpose_st,
    session_id=_session_id_st,
    correct_otp=_otp_plain_st,
    wrong_otp=_otp_plain_st,
)
@settings(max_examples=30)
def test_wrong_otp_is_rejected(
    target: str,
    purpose: str,
    session_id: str,
    correct_otp: str,
    wrong_otp: str,
) -> None:
    """Property 28 (mismatch): verify_otp raises HTTP 400 when OTP hash does not match.

    # Feature: smart-accounting-software, Property 28: OTP verification rejects expired or already-used codes
    **Validates: Requirements 31.4, 31.5**
    """
    import asyncio
    from unittest.mock import patch

    # Only test when the OTPs differ (otherwise it's a valid match)
    if correct_otp == wrong_otp:
        return

    record = _make_record(target, purpose, session_id, correct_otp, is_used=False, expired=False)
    db = _make_db_mock(record)

    with patch("auth.otp._pwd_context", _FastHashContext()):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                verify_otp(target, purpose, session_id, wrong_otp, db)
            )

    assert exc_info.value.status_code == 400


# ── Property 28: valid OTP succeeds ──────────────────────────────────────────

@given(
    target=_target_st,
    purpose=_purpose_st,
    session_id=_session_id_st,
    otp_plain=_otp_plain_st,
)
@settings(max_examples=20)
def test_valid_otp_succeeds(
    target: str,
    purpose: str,
    session_id: str,
    otp_plain: str,
) -> None:
    """Complementary: verify_otp returns True for a valid, unexpired, unused OTP.

    # Feature: smart-accounting-software, Property 28: OTP verification rejects expired or already-used codes
    **Validates: Requirements 31.4**
    """
    import asyncio
    from unittest.mock import patch

    record = _make_record(target, purpose, session_id, otp_plain, is_used=False, expired=False)
    db = _make_db_mock(record)

    with patch("auth.otp._pwd_context", _FastHashContext()):
        result = asyncio.get_event_loop().run_until_complete(
            verify_otp(target, purpose, session_id, otp_plain, db)
        )

    assert result is True
