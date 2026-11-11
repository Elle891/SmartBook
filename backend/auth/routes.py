"""
Public auth routes — no JWT required.

All endpoints use the platform registry database via get_platform_db.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from auth.login import login_with_email, login_with_mobile, verify_login_otp
from auth.otp import resend_otp
from auth.password_reset import (
    request_reset_email,
    request_reset_mobile,
    verify_reset_otp,
)
from auth.registration import (
    register_with_email,
    register_with_mobile,
    verify_registration_otp,
)
from platform.db_router import get_platform_db
from schemas.auth import (
    LoginEmailRequest,
    LoginMobileRequest,
    MobileLoginInitResponse,
    PasswordResetEmailRequest,
    PasswordResetInitResponse,
    PasswordResetMobileRequest,
    PasswordResetResponse,
    RegisterEmailRequest,
    RegisterMobileRequest,
    RegisterResponse,
    ResendOTPRequest,
    ResendOTPResponse,
    TokenResponse,
    VerifyLoginOTPRequest,
    VerifyOTPResponse,
    VerifyRegistrationOTPRequest,
    VerifyResetOTPRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

PlatformDB = AsyncSession  # injected via Depends(get_platform_db)


def _client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Registration ──────────────────────────────────────────────────────────────


@router.post("/register/email", response_model=RegisterResponse, status_code=201)
async def api_register_email(
    body: RegisterEmailRequest,
    request: Request,
    db: PlatformDB = Depends(get_platform_db),
) -> dict:
    return await register_with_email(
        display_name=body.display_name,
        email=body.email,
        password=body.password,
        db=db,
        ip=_client_ip(request),
    )


@router.post("/register/mobile", response_model=RegisterResponse, status_code=201)
async def api_register_mobile(
    body: RegisterMobileRequest,
    request: Request,
    db: PlatformDB = Depends(get_platform_db),
) -> dict:
    return await register_with_mobile(
        display_name=body.display_name,
        mobile=body.mobile,
        password=body.password,
        db=db,
        ip=_client_ip(request),
    )


@router.post("/register/verify-otp", response_model=VerifyOTPResponse)
async def api_verify_registration_otp(
    body: VerifyRegistrationOTPRequest,
    request: Request,
    db: PlatformDB = Depends(get_platform_db),
) -> dict:
    return await verify_registration_otp(
        session_id=body.session_id,
        target=body.target,
        otp=body.otp,
        purpose=body.purpose,
        db=db,
        ip=_client_ip(request),
    )


# ── Login ─────────────────────────────────────────────────────────────────────


@router.post("/login/email", response_model=TokenResponse)
async def api_login_email(
    body: LoginEmailRequest,
    request: Request,
    db: PlatformDB = Depends(get_platform_db),
) -> dict:
    return await login_with_email(
        email=body.email,
        password=body.password,
        db=db,
        ip=_client_ip(request),
    )


@router.post("/login/mobile", response_model=MobileLoginInitResponse)
async def api_login_mobile(
    body: LoginMobileRequest,
    request: Request,
    db: PlatformDB = Depends(get_platform_db),
) -> dict:
    return await login_with_mobile(
        mobile=body.mobile,
        db=db,
        ip=_client_ip(request),
    )


@router.post("/login/verify-otp", response_model=TokenResponse)
async def api_verify_login_otp(
    body: VerifyLoginOTPRequest,
    request: Request,
    db: PlatformDB = Depends(get_platform_db),
) -> dict:
    return await verify_login_otp(
        mobile=body.mobile,
        session_id=body.session_id,
        otp=body.otp,
        db=db,
        ip=_client_ip(request),
    )


# ── Password Reset ────────────────────────────────────────────────────────────


@router.post("/password-reset/email", response_model=PasswordResetInitResponse)
async def api_password_reset_email(
    body: PasswordResetEmailRequest,
    request: Request,
    db: PlatformDB = Depends(get_platform_db),
) -> dict:
    return await request_reset_email(
        email=body.email,
        db=db,
        ip=_client_ip(request),
    )


@router.post("/password-reset/mobile", response_model=PasswordResetInitResponse)
async def api_password_reset_mobile(
    body: PasswordResetMobileRequest,
    request: Request,
    db: PlatformDB = Depends(get_platform_db),
) -> dict:
    return await request_reset_mobile(
        mobile=body.mobile,
        db=db,
        ip=_client_ip(request),
    )


@router.post("/password-reset/verify-otp", response_model=PasswordResetResponse)
async def api_verify_reset_otp(
    body: VerifyResetOTPRequest,
    request: Request,
    db: PlatformDB = Depends(get_platform_db),
) -> dict:
    return await verify_reset_otp(
        target=body.target,
        session_id=body.session_id,
        otp=body.otp,
        new_password=body.new_password,
        purpose=body.purpose,
        db=db,
        ip=_client_ip(request),
    )


# ── OTP Resend ────────────────────────────────────────────────────────────────


@router.post("/otp/resend", response_model=ResendOTPResponse)
async def api_resend_otp(
    body: ResendOTPRequest,
    request: Request,
    db: PlatformDB = Depends(get_platform_db),
) -> dict:
    await resend_otp(
        target=body.target,
        purpose=body.purpose,
        session_id=body.session_id,
        db=db,
    )
    return {"message": "OTP resent"}
