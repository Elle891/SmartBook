"""
AES-256-GCM encryption helpers.

Keys are fetched from HashiCorp Vault via vault_client.get_encryption_key().
Ciphertext format: base64(nonce[12] + ciphertext + tag[16]).
"""

from __future__ import annotations

import base64
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

_NONCE_SIZE = 12  # 96-bit nonce recommended for AES-GCM


def _get_key_bytes(key_name: str) -> bytes:
    """Fetch the AES-256 key from Vault and return raw bytes.

    The key is stored in Vault as a base64-encoded 32-byte value.
    """
    from backend.platform.vault_client import get_vault_client

    vault = get_vault_client()
    key_b64: str = vault.get_encryption_key(key_name)
    key_bytes = base64.b64decode(key_b64)
    if len(key_bytes) != 32:
        raise ValueError(
            f"Encryption key '{key_name}' must be 32 bytes (AES-256); "
            f"got {len(key_bytes)} bytes."
        )
    return key_bytes


def encrypt(plaintext: str, key_name: str) -> str:
    """Encrypt *plaintext* with AES-256-GCM.

    Args:
        plaintext: UTF-8 string to encrypt.
        key_name: Vault key name passed to vault_client.get_encryption_key().

    Returns:
        Base64-encoded string: nonce (12 B) + ciphertext + GCM tag (16 B).
    """
    key_bytes = _get_key_bytes(key_name)
    aesgcm = AESGCM(key_bytes)
    nonce = os.urandom(_NONCE_SIZE)
    # AESGCM.encrypt returns ciphertext + tag concatenated
    ciphertext_and_tag = aesgcm.encrypt(nonce, plaintext.encode(), None)
    blob = nonce + ciphertext_and_tag
    return base64.b64encode(blob).decode()


def decrypt(ciphertext_b64: str, key_name: str) -> str:
    """Decrypt a base64-encoded AES-256-GCM blob.

    Args:
        ciphertext_b64: Base64 string produced by :func:`encrypt`.
        key_name: Vault key name used during encryption.

    Returns:
        Decrypted UTF-8 plaintext.

    Raises:
        cryptography.exceptions.InvalidTag: If authentication fails
            (wrong key or tampered ciphertext).
    """
    key_bytes = _get_key_bytes(key_name)
    aesgcm = AESGCM(key_bytes)
    blob = base64.b64decode(ciphertext_b64)
    nonce = blob[:_NONCE_SIZE]
    ciphertext_and_tag = blob[_NONCE_SIZE:]
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_and_tag, None)
    return plaintext_bytes.decode()
