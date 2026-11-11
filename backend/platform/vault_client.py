"""
HashiCorp Vault client helper using hvac.

Provides read/write operations for secrets used by the accounting platform:
- Bank credentials
- Tenant database connection strings
- Encryption keys (AES-256)
- Service-to-service JWT signing keys
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

import hvac
from hvac.exceptions import InvalidPath, VaultError

logger = logging.getLogger(__name__)

_VAULT_ADDR = os.environ.get("VAULT_ADDR", "http://localhost:8200")
_VAULT_TOKEN = os.environ.get("VAULT_TOKEN", "")
_VAULT_ROLE_ID = os.environ.get("VAULT_ROLE_ID", "")
_VAULT_SECRET_ID = os.environ.get("VAULT_SECRET_ID", "")
_VAULT_MOUNT = os.environ.get("VAULT_MOUNT", "secret")


class VaultClient:
    """Thread-safe wrapper around hvac.Client for KV v2 secrets engine."""

    def __init__(
        self,
        addr: str = _VAULT_ADDR,
        token: str | None = None,
        role_id: str | None = None,
        secret_id: str | None = None,
        mount_point: str = _VAULT_MOUNT,
    ) -> None:
        self._mount = mount_point
        self._client = hvac.Client(url=addr)

        if token:
            self._client.token = token
        elif role_id and secret_id:
            self._approle_login(role_id, secret_id)
        elif _VAULT_TOKEN:
            self._client.token = _VAULT_TOKEN
        else:
            raise VaultError("No Vault authentication method configured.")

        if not self._client.is_authenticated():
            raise VaultError("Vault authentication failed.")

        logger.info("VaultClient authenticated to %s", addr)

    # ── Authentication ────────────────────────────────────────────────────────

    def _approle_login(self, role_id: str, secret_id: str) -> None:
        """Authenticate via AppRole (recommended for production)."""
        result = self._client.auth.approle.login(
            role_id=role_id,
            secret_id=secret_id,
        )
        self._client.token = result["auth"]["client_token"]
        logger.info("VaultClient authenticated via AppRole.")

    def renew_token(self) -> None:
        """Renew the current token lease."""
        self._client.auth.token.renew_self()
        logger.debug("Vault token renewed.")

    # ── KV v2 Operations ─────────────────────────────────────────────────────

    def read_secret(self, path: str) -> dict[str, Any]:
        """
        Read a secret from KV v2.

        Args:
            path: Secret path relative to the mount point (e.g. "bank/tenant-123").

        Returns:
            Dictionary of secret key-value pairs.

        Raises:
            KeyError: If the secret path does not exist.
            VaultError: On Vault communication errors.
        """
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self._mount,
            )
            return response["data"]["data"]  # type: ignore[no-any-return]
        except InvalidPath as exc:
            raise KeyError(f"Vault secret not found: {path}") from exc

    def write_secret(self, path: str, data: dict[str, Any]) -> None:
        """
        Write (create or update) a secret in KV v2.

        Args:
            path: Secret path relative to the mount point.
            data: Dictionary of key-value pairs to store.
        """
        self._client.secrets.kv.v2.create_or_update_secret(
            path=path,
            secret=data,
            mount_point=self._mount,
        )
        logger.debug("Vault secret written: %s", path)

    def delete_secret(self, path: str) -> None:
        """
        Permanently delete all versions of a secret.

        Args:
            path: Secret path relative to the mount point.
        """
        self._client.secrets.kv.v2.delete_metadata_and_all_versions(
            path=path,
            mount_point=self._mount,
        )
        logger.info("Vault secret deleted: %s", path)

    def list_secrets(self, path: str) -> list[str]:
        """
        List secret keys under a path prefix.

        Args:
            path: Path prefix to list.

        Returns:
            List of key names at the given path.
        """
        try:
            response = self._client.secrets.kv.v2.list_secrets(
                path=path,
                mount_point=self._mount,
            )
            return response["data"]["keys"]  # type: ignore[no-any-return]
        except InvalidPath:
            return []

    # ── Convenience helpers ───────────────────────────────────────────────────

    def get_bank_credentials(self, account_set_id: str, bank_code: str) -> dict[str, Any]:
        """Retrieve bank credentials for a given account set and bank."""
        path = f"bank/{account_set_id}/{bank_code}"
        return self.read_secret(path)

    def store_bank_credentials(
        self, account_set_id: str, bank_code: str, credentials: dict[str, Any]
    ) -> None:
        """Store bank credentials for a given account set and bank."""
        path = f"bank/{account_set_id}/{bank_code}"
        self.write_secret(path, credentials)

    def get_tenant_db_credentials(self, account_set_id: str) -> dict[str, Any]:
        """Retrieve tenant database credentials from Vault."""
        path = f"tenant-db/{account_set_id}"
        return self.read_secret(path)

    def store_tenant_db_credentials(
        self, account_set_id: str, credentials: dict[str, Any]
    ) -> None:
        """Store tenant database credentials in Vault."""
        path = f"tenant-db/{account_set_id}"
        self.write_secret(path, credentials)

    def get_encryption_key(self, key_name: str) -> str:
        """Retrieve an AES-256 encryption key by name."""
        path = f"encryption-keys/{key_name}"
        secret = self.read_secret(path)
        return secret["key"]  # type: ignore[no-any-return]

    def store_encryption_key(self, key_name: str, key_value: str) -> None:
        """Store an AES-256 encryption key."""
        path = f"encryption-keys/{key_name}"
        self.write_secret(path, {"key": key_value})

    def get_jwt_signing_key(self, service: str) -> dict[str, str]:
        """Retrieve RSA key pair for JWT signing (private + public PEM)."""
        path = f"jwt-keys/{service}"
        return self.read_secret(path)

    def store_jwt_signing_key(
        self, service: str, private_pem: str, public_pem: str
    ) -> None:
        """Store RSA key pair for JWT signing."""
        path = f"jwt-keys/{service}"
        self.write_secret(path, {"private_key": private_pem, "public_key": public_pem})


@lru_cache(maxsize=1)
def get_vault_client() -> VaultClient:
    """
    Return a cached singleton VaultClient.

    Uses AppRole auth when VAULT_ROLE_ID + VAULT_SECRET_ID are set,
    otherwise falls back to token auth (dev/test only).
    """
    return VaultClient(
        addr=_VAULT_ADDR,
        token=_VAULT_TOKEN or None,
        role_id=_VAULT_ROLE_ID or None,
        secret_id=_VAULT_SECRET_ID or None,
    )
