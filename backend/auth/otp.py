"""
OTP generation, verification, and resend with rate limiting.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import OTPRecord

logger = logging.getLogger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_OTP_TTL_MINUTES = 10
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_TTL = 3600  # 1 hour


@lru_cache(maxsize=1)
def _get_redis() -> aioredis.Redis:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return aioredis.from_url(url, decode_responses=True)


async def _check_rate_limit(target: str) -> None:
    """Enforce max 5 OTP sends per target per hour (Requirements 31.13)."""
    redis = _get_redis()
    rate_key = f"otp_rate:{target}"
    count = await redis.incr(rate_key)
    if count == 1:
        await redis.expire(rate_key, _RATE_LIMIT_TTL)
    if count > _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OTP send rate limit exceeded. Try again later.",
        )


async def send_otp(
    target: str,
    purpose: str,
    session_id: str,
    db: AsyncSession,
) -> str:
    """Generate, store, and send a 6-digit OTP."""
    await _check_rate_limit(target)

    otp_plain = f"{secrets.randbelow(1_000_000):06d}"
    otp_hash = _pwd_context.hash(otp_plain)

    await db.execute(
        update(OTPRecord)
        .where(
            OTPRecord.target == target,
            OTPRecord.purpose == purpose,
            OTPRecord.session_id == session_id,
            OTPRecord.is_used.is_(False),
        )
        .values(is_used=True)
    )

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_OTP_TTL_MINUTES)
    record = OTPRecord(
        target=target,
        otp_hash=otp_hash,
        purpose=purpose,
        session_id=session_id,
        is_used=False,
        expires_at=expires_at,
    )
    db.add(record)
    await db.flush()

    if "@" in target:
        from notifications.email import send_email

        await send_email(
            to=target,
            subject="Your verification code",
            body=(
                f"Your verification code is: {otp_plain}\n"
                f"Valid for {_OTP_TTL_MINUTES} minutes."
            ),
        )
    else:
        from notifications.sms import send_sms

        await send_sms(to=target, message=otp_plain)

    logger.info("OTP sent to %s for purpose=%s", target, purpose)
    return otp_plain


async def verify_otp(
    target: str,
    purpose: str,
    session_id: str,
    otp_plain: str,
    db: AsyncSession,
) -> bool:
    """Verify a submitted OTP; mark used on success."""
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(OTPRecord)
        .where(
            OTPRecord.target == target,
            OTPRecord.purpose == purpose,
            OTPRecord.session_id == session_id,
            OTPRecord.is_used.is_(False),
            OTPRecord.expires_at > now,
        )
        .order_by(OTPRecord.created_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP not found or expired.",
        )

    if not _pwd_context.verify(otp_plain, record.otp_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP.",
        )

    record.is_used = True
    await db.flush()
    return True


async def resend_otp(
    target: str,
    purpose: str,
    session_id: str,
    db: AsyncSession,
) -> str:
    """Resend OTP (rate limiting applied inside send_otp)."""
    return await send_otp(target, purpose, session_id, db)
