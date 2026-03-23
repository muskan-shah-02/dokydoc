"""
Encryption Service — Transparent encryption/decryption for sensitive fields.
Sprint 6: Data Encryption at Rest.

Encrypts sensitive fields (raw_text, structured_data) using Fernet symmetric encryption.
Key is managed via environment config (ENCRYPTION_KEY).
"""
import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet

from app.core.logging import get_logger

logger = get_logger("encryption_service")

# Marker prefix for encrypted values so we can detect already-encrypted data
ENCRYPTED_PREFIX = "enc::"


def _get_fernet() -> Optional[Fernet]:
    """Get Fernet instance from environment key, or None if not configured."""
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        return None
    # Ensure key is valid Fernet key (32 url-safe base64 bytes)
    # If raw string provided, derive a proper key from it
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        # Derive a proper Fernet key from arbitrary string
        derived = base64.urlsafe_b64encode(
            hashlib.sha256(key.encode()).digest()
        )
        return Fernet(derived)


def encrypt(plaintext: str) -> str:
    """
    Encrypt a plaintext string. Returns the ciphertext prefixed with 'enc::'.
    If no encryption key is configured, returns the plaintext unchanged.
    """
    if not plaintext:
        return plaintext
    if plaintext.startswith(ENCRYPTED_PREFIX):
        return plaintext  # Already encrypted

    fernet = _get_fernet()
    if not fernet:
        return plaintext  # Encryption not configured

    try:
        token = fernet.encrypt(plaintext.encode("utf-8"))
        return ENCRYPTED_PREFIX + token.decode("utf-8")
    except Exception as e:
        logger.warning(f"Encryption failed (returning plaintext): {e}")
        return plaintext


def decrypt(ciphertext: str) -> str:
    """
    Decrypt a ciphertext string. If the value doesn't have the 'enc::' prefix,
    it's treated as plaintext and returned as-is.
    If no encryption key is configured, returns the value unchanged.
    """
    if not ciphertext:
        return ciphertext
    if not ciphertext.startswith(ENCRYPTED_PREFIX):
        return ciphertext  # Not encrypted

    fernet = _get_fernet()
    if not fernet:
        logger.warning("Cannot decrypt: ENCRYPTION_KEY not configured")
        return ciphertext

    try:
        token = ciphertext[len(ENCRYPTED_PREFIX):].encode("utf-8")
        return fernet.decrypt(token).decode("utf-8")
    except Exception as e:
        logger.warning(f"Decryption failed (returning raw value): {e}")
        return ciphertext


def is_encryption_configured() -> bool:
    """Check if encryption is configured."""
    return os.getenv("ENCRYPTION_KEY") is not None


def generate_key() -> str:
    """Generate a new Fernet key for use as ENCRYPTION_KEY."""
    return Fernet.generate_key().decode("utf-8")
