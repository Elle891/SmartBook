"""
RS256 JWT issue/verify with 15-minute inactivity timeout.

Keys are loaded from HashiCorp Vault (path: jwt-keys/svc-accounting).
Falls back to env vars JWT_PRIVATE_KEY / JWT_PUBLIC_KEY for dev/test.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

logger = logging.getLogger(__name__)

_ALGORITHM = "RS256"
_BEARER = HTTPBearer(auto_error=True)
_dev_keys: tuple[str, str] | None = None


def _generate_dev_rsa_keys() -> tuple[str, str]:
    """Generate ephemeral RSA key pair for local dev / CI tests."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def _load_keys() -> tuple[str, str]:
    """Return (private_key_pem, public_key_pem)."""
    global _dev_keys

    private_key = os.environ.get("JWT_PRIVATE_KEY", "")
    public_key = os.environ.get("JWT_PUBLIC_KEY", "")

    if not private_key or not public_key:
        try:
            from platform.vault_client import get_vault_client

            vault = get_vault_client()
            keys = vault.get_jwt_signing_key("svc-accounting")
            private_key = keys["private_key"]
            public_key = keys["public_key"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load JWT keys from Vault: %s", exc)

    if not private_key or not public_key:
        env = os.environ.get("ENVIRONMENT", "development").lower()
        if env in ("development", "test", "dev"):
            if _dev_keys is None:
                _dev_keys = _generate_dev_rsa_keys()
                logger.info("Using auto-generated JWT keys for %s environment", env)
            return _dev_keys
        raise RuntimeError(
            "JWT keys not configured. Set JWT_PRIVATE_KEY / JWT_PUBLIC_KEY "
            "or configure Vault at jwt-keys/svc-accounting."
        )

    return private_key, public_key


def issue_token(
    user_id: str,
    account_set_id: str,
    role: str,
    session_id: str,
    expires_in: int = 900,
) -> str:
    """Issue a signed RS256 JWT."""
    import time

    private_key, _ = _load_keys()
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "account_set_id": account_set_id,
        "role": role,
        "session_id": session_id,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, private_key, algorithm=_ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    """Verify and decode a JWT."""
    _, public_key = _load_keys()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            public_key,
            algorithms=[_ALGORITHM],
        )
        return payload
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_BEARER),
) -> dict[str, Any]:
    """FastAPI dependency that returns the decoded user payload."""
    token = credentials.credentials
    payload = verify_token(token)

    session_id: str | None = payload.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing session identifier.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from auth.session import is_session_valid, touch_session

    if not await is_session_valid(session_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired due to inactivity.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str = payload.get("sub", "")
    await touch_session(user_id, session_id)

    # Expose both JWT claim name (`sub`) and app alias (`user_id`).
    return {
        "sub": user_id,
        "user_id": user_id,
        "account_set_id": payload.get("account_set_id", ""),
        "role": payload.get("role", ""),
        "session_id": session_id,
    }
