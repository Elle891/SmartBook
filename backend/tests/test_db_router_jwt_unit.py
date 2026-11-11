"""Unit tests for JWT claim extract and shared tenant URL helpers."""

from __future__ import annotations

import importlib

import pytest
from jose import jwt


def test_decode_account_set_id_empty_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    import platform.db_router as router

    importlib.reload(router)

    token = jwt.encode(
        {"sub": "u1", "account_set_id": "", "role": "", "session_id": "s"},
        key="unused",
        algorithm="HS256",
    )
    assert router._decode_account_set_id(f"Bearer {token}") is None


def test_decode_account_set_id_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    import platform.db_router as router

    importlib.reload(router)

    token = jwt.encode(
        {
            "sub": "u1",
            "account_set_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "role": "Viewer",
            "session_id": "s",
        },
        key="unused",
        algorithm="HS256",
    )
    assert (
        router._decode_account_set_id(f"Bearer {token}")
        == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    )


def test_resolve_shared_tenant_db_url_mysql(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_DB_TYPE", "mysql")
    monkeypatch.setenv("PLATFORM_DB_HOST", "localhost")
    monkeypatch.setenv("PLATFORM_DB_PORT", "3306")
    monkeypatch.setenv("PLATFORM_DB_USER", "smartbook")
    monkeypatch.setenv("PLATFORM_DB_PASSWORD", "smartbook")
    monkeypatch.delenv("SHARED_TENANT_DB_URL", raising=False)
    monkeypatch.delenv("TENANT_DB_URL", raising=False)
    monkeypatch.delenv("PLATFORM_DB_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from platform.db_config import resolve_shared_tenant_db_url

    url = resolve_shared_tenant_db_url()
    assert url.startswith("mysql+aiomysql://")
    assert url.endswith("/smartbook_shared")
