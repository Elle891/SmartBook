"""
Pydantic v2 request/response schemas for auth endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


# ── Registration ──────────────────────────────────────────────────────────────

class RegisterEmailRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=128)
    email: EmailStr
    password: str = Field(min_length=8)


class RegisterMobileRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=128)
    mobile: str = Field(min_length=7, max_length=20)
    password: str = Field(min_length=8)


class VerifyRegistrationOTPRequest(BaseModel):
    target: str  # email or mobile
    session_id: str
    otp: str = Field(min_length=6, max_length=6)
    purpose: str  # "register_email" | "register_mobile"


class RegisterResponse(BaseModel):
    user_id: str
    session_id: str
    message: str


class VerifyOTPResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginEmailRequest(BaseModel):
    email: EmailStr
    password: str


class LoginMobileRequest(BaseModel):
    mobile: str


class VerifyLoginOTPRequest(BaseModel):
    mobile: str
    session_id: str
    otp: str = Field(min_length=6, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MobileLoginInitResponse(BaseModel):
    session_id: str
    message: str


# ── Password Reset ────────────────────────────────────────────────────────────

class PasswordResetEmailRequest(BaseModel):
    email: EmailStr


class PasswordResetMobileRequest(BaseModel):
    mobile: str


class VerifyResetOTPRequest(BaseModel):
    target: str  # email or mobile
    session_id: str
    otp: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8)
    purpose: str  # "reset_email" | "reset_mobile"


class PasswordResetInitResponse(BaseModel):
    session_id: str
    message: str


class PasswordResetResponse(BaseModel):
    message: str


# ── OTP Resend ────────────────────────────────────────────────────────────────

class ResendOTPRequest(BaseModel):
    target: str
    purpose: str
    session_id: str


class ResendOTPResponse(BaseModel):
    message: str
