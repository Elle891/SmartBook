"""
Vault storage for bank credentials and routing params (Req 2.2, 25.5).
Credentials MUST NOT be stored in the main database.
"""

from __future__ import annotations

from typing import Any


def _get_vault():
    from platform.vault_client import get_vault_client

    return get_vault_client()


def credentials_vault_path(account_set_id: str, connection_id: str) -> str:
    return f"bank/{account_set_id}/connections/{connection_id}"


def store_connection_credentials(
    account_set_id: str,
    connection_id: str,
    credentials: dict[str, Any],
) -> str:
    path = credentials_vault_path(account_set_id, connection_id)
    _get_vault().write_secret(path, credentials)
    return path


def read_connection_credentials(path: str) -> dict[str, Any]:
    return _get_vault().read_secret(path)


def store_routing_params(path: str, params: dict[str, Any]) -> None:
    _get_vault().write_secret(path, params)


def read_routing_params(path: str) -> dict[str, Any]:
    return _get_vault().read_secret(path)
