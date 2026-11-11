"""Unit tests for platform DB URL resolution."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_DB_CONFIG_PATH = _BACKEND_DIR / "platform" / "db_config.py"
_spec = importlib.util.spec_from_file_location("smartbook_db_config", _DB_CONFIG_PATH)
assert _spec and _spec.loader
_db_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_db_config)

get_platform_db_type = _db_config.get_platform_db_type
resolve_platform_db_url = _db_config.resolve_platform_db_url
resolve_platform_db_url_sync = _db_config.resolve_platform_db_url_sync


@pytest.fixture(autouse=True)
def _clear_platform_db_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "PLATFORM_DB_TYPE",
        "PLATFORM_DB_URL",
        "REGISTRY_DB_URL",
        "DATABASE_URL",
        "PLATFORM_DB_HOST",
        "PLATFORM_DB_PORT",
        "PLATFORM_DB_USER",
        "PLATFORM_DB_PASSWORD",
        "PLATFORM_DB_NAME",
    ):
        monkeypatch.delenv(key, raising=False)


def test_defaults_to_mysql() -> None:
    assert get_platform_db_type() == "mysql"
    assert resolve_platform_db_url().startswith("mysql+aiomysql://")


def test_postgresql_from_platform_db_type() -> None:
    os.environ["PLATFORM_DB_TYPE"] = "postgresql"
    os.environ["PLATFORM_DB_HOST"] = "db.example"
    os.environ["PLATFORM_DB_USER"] = "app"
    os.environ["PLATFORM_DB_PASSWORD"] = "secret"
    assert get_platform_db_type() == "postgresql"
    url = resolve_platform_db_url()
    assert url.startswith("postgresql+asyncpg://")
    assert "app:secret@db.example:5432/platform_registry" in url
    assert resolve_platform_db_url_sync().startswith("postgresql://")


def test_mysql_from_platform_db_type() -> None:
    os.environ["PLATFORM_DB_TYPE"] = "mysql"
    os.environ["PLATFORM_DB_HOST"] = "db.example"
    os.environ["PLATFORM_DB_USER"] = "app"
    os.environ["PLATFORM_DB_PASSWORD"] = "secret"
    assert get_platform_db_type() == "mysql"
    url = resolve_platform_db_url()
    assert url.startswith("mysql+aiomysql://")
    assert "app:secret@db.example:3306/platform_registry" in url
    assert resolve_platform_db_url_sync().startswith("mysql+pymysql://")


def test_explicit_database_url_wins() -> None:
    os.environ["DATABASE_URL"] = (
        "mysql+aiomysql://smartbook:smartbook@localhost:3306/platform_registry"
    )
    assert get_platform_db_type() == "mysql"
    assert resolve_platform_db_url().startswith("mysql+aiomysql://")
