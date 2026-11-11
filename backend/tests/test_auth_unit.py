"""
Unit tests for auth: rate limiting, account lockout, password strength,
and duplicate registration rejection.

_Requirements: 31.6, 31.7, 31.13, 31.14_
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from auth.registration import _validate_password_strength


# ── Password strength enforcement (Requirement 31.7) ─────────────────────────

class TestPasswordStrength:
    def test_too_short(self):
        with pytest.raises(HTTPException) as exc:
            _validate_password_strength("Ab1!")
        assert exc.value.status_code == 422

    def test_no_uppercase(self):
        with pytest.raises(HTTPException) as exc:
            _validate_password_strength("abcdef1!")
        assert exc.value.status_code == 422

    def test_no_lowercase(self):
        with pytest.raises(HTTPException) as exc:
            _validate_password_strength("ABCDEF1!")
        assert exc.value.status_code == 422

    def test_no_digit(self):
        with pytest.raises(HTTPException) as exc:
            _validate_password_strength("Abcdefg!")
        assert exc.value.status_code == 422

    def test_no_special_char(self):
        with pytest.raises(HTTPException) as exc:
            _validate_password_strength("Abcdef12")
        assert exc.value.status_code == 422

    def test_valid_password(self):
        _validate_password_strength("Abcdef1!")

    def test_valid_password_various_specials(self):
        for special in ["@", "#", "$", "%", "^", "&", "*", "(", ")", "-", "_"]:
            _validate_password_strength(f"Abcdef1{special}")

    def test_exactly_8_chars_valid(self):
        _validate_password_strength("Abcde1!x")

    def test_7_chars_invalid(self):
        with pytest.raises(HTTPException):
            _validate_password_strength("Abc1!xy")


# ── Duplicate registration rejection (Requirement 31.6) ──────────────────────

class TestDuplicateRegistration:
    @pytest.mark.asyncio
    async def test_duplicate_email_rejected(self):
        from auth.registration import register_with_email
        from models.user import User

        existing_user = MagicMock(spec=User)
        db = AsyncMock()
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = existing_user
        db.execute = AsyncMock(return_value=scalar_result)

        with pytest.raises(HTTPException) as exc:
            await register_with_email(
                display_name="Test User",
                email="test@example.com",
                password="Abcdef1!",
                db=db,
                ip="127.0.0.1",
            )
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_duplicate_mobile_rejected(self):
        from auth.registration import register_with_mobile
        from models.user import User

        existing_user = MagicMock(spec=User)
        db = AsyncMock()
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = existing_user
        db.execute = AsyncMock(return_value=scalar_result)

        with pytest.raises(HTTPException) as exc:
            await register_with_mobile(
                display_name="Test User",
                mobile="13800138000",
                password="Abcdef1!",
                db=db,
                ip="127.0.0.1",
            )
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_invalid_email_rejected(self):
        from auth.registration import register_with_email

        db = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await register_with_email(
                display_name="Test User",
                email="not-an-email",
                password="Abcdef1!",
                db=db,
                ip="127.0.0.1",
            )
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_mobile_rejected(self):
        from auth.registration import register_with_mobile

        db = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await register_with_mobile(
                display_name="Test User",
                mobile="123",
                password="Abcdef1!",
                db=db,
                ip="127.0.0.1",
            )
        assert exc.value.status_code == 422


# ── Account lockout (Requirement 31.14) ──────────────────────────────────────

class TestAccountLockout:
    def _make_user(self, *, failed_attempts: int = 0, locked_until=None, is_active: bool = True):
        from models.user import User

        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.email = "test@example.com"
        user.password_hash = "$2b$12$placeholder"
        user.failed_login_attempts = failed_attempts
        user.locked_until = locked_until
        user.is_active = is_active
        return user

    def _make_db(self, user):
        db = AsyncMock()
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = user
        db.execute = AsyncMock(return_value=scalar_result)
        db.flush = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_locked_account_raises_423(self):
        from auth.login import login_with_email

        locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        user = self._make_user(locked_until=locked_until)
        db = self._make_db(user)

        with pytest.raises(HTTPException) as exc:
            await login_with_email("test@example.com", "anypassword", db, "127.0.0.1")
        assert exc.value.status_code == 423

    @pytest.mark.asyncio
    async def test_failed_attempts_increment_on_wrong_password(self):
        from auth.login import login_with_email

        user = self._make_user(failed_attempts=0)
        db = self._make_db(user)

        with patch("auth.login._pwd_context") as mock_ctx:
            mock_ctx.verify.return_value = False

            with pytest.raises(HTTPException) as exc:
                await login_with_email("test@example.com", "wrongpass", db, "127.0.0.1")

        assert exc.value.status_code == 401
        assert user.failed_login_attempts == 1

    @pytest.mark.asyncio
    async def test_account_locked_after_10_failures(self):
        from auth.login import login_with_email

        user = self._make_user(failed_attempts=9)
        db = self._make_db(user)

        with patch("auth.login._pwd_context") as mock_ctx:
            mock_ctx.verify.return_value = False

            with pytest.raises(HTTPException) as exc:
                await login_with_email("test@example.com", "wrongpass", db, "127.0.0.1")

        assert exc.value.status_code == 401
        assert user.failed_login_attempts == 10
        assert user.locked_until is not None

    @pytest.mark.asyncio
    async def test_lockout_expires_allows_login(self):
        from auth.login import login_with_email

        locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        user = self._make_user(failed_attempts=10, locked_until=locked_until)
        db = self._make_db(user)

        with patch("auth.login._pwd_context") as mock_ctx, \
             patch("auth.login.touch_session", new_callable=AsyncMock), \
             patch("auth.login.issue_token", return_value="token"), \
             patch("auth.login.write_audit", new_callable=AsyncMock):
            mock_ctx.verify.return_value = True

            result = await login_with_email("test@example.com", "Abcdef1!", db, "127.0.0.1")

        assert result["access_token"] == "token"
        assert user.failed_login_attempts == 0
        assert user.locked_until is None

    @pytest.mark.asyncio
    async def test_unknown_email_returns_401(self):
        from auth.login import login_with_email

        db = AsyncMock()
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=scalar_result)

        with pytest.raises(HTTPException) as exc:
            await login_with_email("unknown@example.com", "Abcdef1!", db, "127.0.0.1")
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_inactive_account_cannot_login(self):
        from auth.login import login_with_email

        user = self._make_user(is_active=False)
        db = self._make_db(user)

        with pytest.raises(HTTPException) as exc:
            await login_with_email("test@example.com", "Abcdef1!", db, "127.0.0.1")
        assert exc.value.status_code == 401


# ── OTP rate limiting (Requirement 31.13) ────────────────────────────────────

class TestOTPRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_raises_429(self):
        from auth.otp import resend_otp

        db = AsyncMock()

        with patch("auth.otp._get_redis") as mock_redis_factory:
            mock_redis = AsyncMock()
            mock_redis.incr = AsyncMock(return_value=6)
            mock_redis.expire = AsyncMock()
            mock_redis_factory.return_value = mock_redis

            with pytest.raises(HTTPException) as exc:
                await resend_otp("test@example.com", "register_email", "sess-1", db)

        assert exc.value.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_not_exceeded_sends_otp(self):
        from auth.otp import resend_otp

        db = AsyncMock()

        with patch("auth.otp._get_redis") as mock_redis_factory, \
             patch("auth.otp.send_otp", new_callable=AsyncMock, return_value="123456") as mock_send:
            mock_redis = AsyncMock()
            mock_redis.incr = AsyncMock(return_value=1)
            mock_redis.expire = AsyncMock()
            mock_redis_factory.return_value = mock_redis

            result = await resend_otp("test@example.com", "register_email", "sess-1", db)

        assert result == "123456"
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_exactly_5_sends_allowed(self):
        from auth.otp import resend_otp

        db = AsyncMock()

        with patch("auth.otp._get_redis") as mock_redis_factory, \
             patch("auth.otp.send_otp", new_callable=AsyncMock, return_value="000000"):
            mock_redis = AsyncMock()
            mock_redis.incr = AsyncMock(return_value=5)
            mock_redis.expire = AsyncMock()
            mock_redis_factory.return_value = mock_redis

            result = await resend_otp("test@example.com", "register_email", "sess-1", db)

        assert result == "000000"


# ── Registration verify issues JWT (Requirement 31.8) ────────────────────────

class TestRegistrationVerify:
    @pytest.mark.asyncio
    async def test_verify_registration_returns_jwt(self):
        from auth.registration import verify_registration_otp
        from models.user import User

        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.is_email_verified = False
        user.is_active = False

        db = AsyncMock()
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = user
        db.execute = AsyncMock(return_value=scalar_result)
        db.flush = AsyncMock()

        with patch("auth.registration.verify_otp", new_callable=AsyncMock), \
             patch("auth.registration.touch_session", new_callable=AsyncMock), \
             patch("auth.registration.issue_token", return_value="jwt-token"), \
             patch("auth.registration.write_audit", new_callable=AsyncMock):
            result = await verify_registration_otp(
                session_id="sess-1",
                target="user@example.com",
                otp="123456",
                purpose="register_email",
                db=db,
                ip="127.0.0.1",
            )

        assert result["access_token"] == "jwt-token"
        assert user.is_active is True
        assert user.is_email_verified is True
