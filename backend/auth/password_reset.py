"""
Password reset service: request OTP and verify to set new password.
"""

from __future__ import annotations

import logging
import uuid

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from audit.service import write_audit
from auth.otp import send_otp, verify_otp
from auth.registration import (
    _normalize_email,
    _normalize_mobile,
    _validate_password_strength,
)
from models.user import User

logger = logging.getLogger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def request_reset_email(
    email: str,
    db: AsyncSession,
    ip: str,
) -> dict:
    """Request a password reset OTP for an email address."""
    email = _normalize_email(email)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    session_id = str(uuid.uuid4())

    if user is not None:
        await send_otp(email, "reset_email", session_id, db)
        await write_audit(
            db,
            user_id=str(user.id),
            action="user.password_reset_requested",
            entity_type="User",
            entity_id=str(user.id),
            ip_address=ip,
        )

    return {
        "session_id": session_id,
        "message": "If the email exists, an OTP has been sent",
    }


async def request_reset_mobile(
    mobile: str,
    db: AsyncSession,
    ip: str,
) -> dict:
    """Request a password reset OTP for a mobile number."""
    mobile = _normalize_mobile(mobile)
    result = await db.execute(select(User).where(User.mobile == mobile))
    user = result.scalar_one_or_none()

    session_id = str(uuid.uuid4())

    if user is not None:
        await send_otp(mobile, "reset_mobile", session_id, db)
        await write_audit(
            db,
            user_id=str(user.id),
            action="user.password_reset_requested",
            entity_type="User",
            entity_id=str(user.id),
            ip_address=ip,
        )

    return {
        "session_id": session_id,
        "message": "If the mobile exists, an OTP has been sent",
    }


async def verify_reset_otp(
    target: str,
    session_id: str,
    otp: str,
    new_password: str,
    purpose: str,
    db: AsyncSession,
    ip: str,
) -> dict:
    """Verify reset OTP and update the user's password."""
    if "@" in target:
        target = _normalize_email(target)
    else:
        target = _normalize_mobile(target)

    await verify_otp(target, purpose, session_id, otp, db)

    _validate_password_strength(new_password)

    if "@" in target:
        result = await db.execute(select(User).where(User.email == target))
    else:
        result = await db.execute(select(User).where(User.mobile == target))

    user = result.scalar_one_or_none()
    if user is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    user.password_hash = _pwd_context.hash(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.flush()

    await write_audit(
        db,
        user_id=str(user.id),
        action="user.password_reset",
        entity_type="User",
        entity_id=str(user.id),
        ip_address=ip,
    )

    return {"message": "Password reset successful"}
