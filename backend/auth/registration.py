"""
User registration service: email and mobile registration with OTP verification.
"""

from __future__ import annotations

import logging
import re
import uuid

from fastapi import HTTPException, status
from passlib.context import CryptContext
from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from audit.service import write_audit
from auth.jwt import issue_token
from auth.otp import send_otp, verify_otp
from auth.session import touch_session
from models.user import User

logger = logging.getLogger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_email_adapter = TypeAdapter(EmailStr)

# E.164 or Chinese mobile (11 digits starting with 1)
_MOBILE_RE = re.compile(r"^\+?[1-9]\d{6,14}$|^1[3-9]\d{9}$")


def _validate_password_strength(password: str) -> None:
    """Enforce password policy: min 8 chars, upper, lower, digit, special."""
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters.",
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one uppercase letter.",
        )
    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one lowercase letter.",
        )
    if not re.search(r"\d", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one digit.",
        )
    if not re.search(r"[^A-Za-z0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one special character.",
        )


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _normalize_mobile(mobile: str) -> str:
    return mobile.strip()


async def register_with_email(
    display_name: str,
    email: str,
    password: str,
    db: AsyncSession,
    ip: str,
) -> dict:
    """Register a new user with email + password, send verification OTP."""
    display_name = display_name.strip()
    if not display_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Display name is required.",
        )

    email = _normalize_email(email)
    try:
        _email_adapter.validate_python(email)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email address.",
        )

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )

    _validate_password_strength(password)

    password_hash = _pwd_context.hash(password)
    user = User(
        display_name=display_name,
        email=email,
        password_hash=password_hash,
        is_active=False,
        is_email_verified=False,
    )
    db.add(user)
    await db.flush()

    session_id = str(uuid.uuid4())
    await send_otp(email, "register_email", session_id, db)

    await write_audit(
        db,
        user_id=str(user.id),
        action="user.register_email_initiated",
        entity_type="User",
        entity_id=str(user.id),
        ip_address=ip,
    )

    return {
        "user_id": str(user.id),
        "session_id": session_id,
        "message": "OTP sent to email",
    }


async def register_with_mobile(
    display_name: str,
    mobile: str,
    password: str,
    db: AsyncSession,
    ip: str,
) -> dict:
    """Register a new user with mobile + password, send verification OTP."""
    display_name = display_name.strip()
    if not display_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Display name is required.",
        )

    mobile = _normalize_mobile(mobile)
    if not _MOBILE_RE.match(mobile):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid mobile number format.",
        )

    existing = await db.execute(select(User).where(User.mobile == mobile))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mobile number already registered.",
        )

    _validate_password_strength(password)

    password_hash = _pwd_context.hash(password)
    user = User(
        display_name=display_name,
        mobile=mobile,
        password_hash=password_hash,
        is_active=False,
        is_mobile_verified=False,
    )
    db.add(user)
    await db.flush()

    session_id = str(uuid.uuid4())
    await send_otp(mobile, "register_mobile", session_id, db)

    await write_audit(
        db,
        user_id=str(user.id),
        action="user.register_mobile_initiated",
        entity_type="User",
        entity_id=str(user.id),
        ip_address=ip,
    )

    return {
        "user_id": str(user.id),
        "session_id": session_id,
        "message": "OTP sent to mobile",
    }


async def verify_registration_otp(
    session_id: str,
    target: str,
    otp: str,
    purpose: str,
    db: AsyncSession,
    ip: str,
) -> dict:
    """Verify registration OTP, activate the user, and issue a JWT (auto-login)."""
    target = target.strip()
    if "@" in target:
        target = _normalize_email(target)
    else:
        target = _normalize_mobile(target)

    await verify_otp(target, purpose, session_id, otp, db)

    if "@" in target:
        result = await db.execute(select(User).where(User.email == target))
    else:
        result = await db.execute(select(User).where(User.mobile == target))

    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if purpose == "register_email":
        user.is_email_verified = True
    elif purpose == "register_mobile":
        user.is_mobile_verified = True
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid registration purpose.",
        )

    user.is_active = True
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.flush()

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
        action="user.registered",
        entity_type="User",
        entity_id=str(user.id),
        ip_address=ip,
    )

    return {
        "message": "Registration complete",
        "access_token": token,
        "token_type": "bearer",
    }
