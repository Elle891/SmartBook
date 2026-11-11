"""
Login service: email/password login and mobile OTP login.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from audit.service import write_audit
from auth.jwt import issue_token
from auth.otp import send_otp, verify_otp
from auth.registration import _normalize_email, _normalize_mobile
from auth.session import touch_session
from models.user import User

logger = logging.getLogger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_MAX_FAILED_ATTEMPTS = 10
_LOCKOUT_MINUTES = 15


async def login_with_email(
    email: str,
    password: str,
    db: AsyncSession,
    ip: str,
) -> dict:
    """Authenticate with email + password, return JWT on success."""
    email = _normalize_email(email)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked until {user.locked_until.isoformat()}.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is not active. Complete registration first.",
        )

    if not user.password_hash or not _pwd_context.verify(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= _MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=_LOCKOUT_MINUTES)
            logger.warning(
                "Account locked for user %s after %d failures",
                user.id,
                user.failed_login_attempts,
            )
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    user.failed_login_attempts = 0
    user.locked_until = None
    await db.flush()

    session_id = str(uuid.uuid4())
    await touch_session(str(user.id), session_id)
    token = issue_token(
        user_id=str(user.id),
        account_set_id="",
        role="",
        session_id=session_id,
    )

    await write_audit(
        db,
        user_id=str(user.id),
        action="user.login_email",
        entity_type="User",
        entity_id=str(user.id),
        ip_address=ip,
    )

    return {"access_token": token, "token_type": "bearer"}


async def login_with_mobile(
    mobile: str,
    db: AsyncSession,
    ip: str,
) -> dict:
    """Initiate mobile OTP login — sends OTP to the mobile number."""
    mobile = _normalize_mobile(mobile)
    result = await db.execute(select(User).where(User.mobile == mobile))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mobile number not registered.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is not active. Complete registration first.",
        )

    session_id = str(uuid.uuid4())
    await send_otp(mobile, "login_mobile", session_id, db)

    await write_audit(
        db,
        user_id=str(user.id),
        action="user.login_mobile_initiated",
        entity_type="User",
        entity_id=str(user.id),
        ip_address=ip,
    )

    return {"session_id": session_id, "message": "OTP sent to mobile"}


async def verify_login_otp(
    mobile: str,
    session_id: str,
    otp: str,
    db: AsyncSession,
    ip: str,
) -> dict:
    """Verify mobile OTP and return JWT on success."""
    mobile = _normalize_mobile(mobile)
    await verify_otp(mobile, "login_mobile", session_id, otp, db)

    result = await db.execute(select(User).where(User.mobile == mobile))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    new_session_id = str(uuid.uuid4())
    await touch_session(str(user.id), new_session_id)
    token = issue_token(
        user_id=str(user.id),
        account_set_id="",
        role="",
        session_id=new_session_id,
    )

    await write_audit(
        db,
        user_id=str(user.id),
        action="user.login_mobile",
        entity_type="User",
        entity_id=str(user.id),
        ip_address=ip,
    )

    return {"access_token": token, "token_type": "bearer"}
