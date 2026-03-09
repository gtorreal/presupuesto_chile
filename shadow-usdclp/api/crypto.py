"""
Symmetric encryption for service credentials stored in the database.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` library.
The master key must be set via CREDENTIAL_MASTER_KEY env var.

Generate a key with:
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os

from cryptography.fernet import Fernet

_MASTER_KEY = os.environ.get("CREDENTIAL_MASTER_KEY", "")

if _MASTER_KEY:
    _fernet = Fernet(_MASTER_KEY.encode())
else:
    _fernet = None


def is_configured() -> bool:
    return _fernet is not None


def encrypt(plaintext: str) -> str:
    if not _fernet:
        raise RuntimeError("CREDENTIAL_MASTER_KEY not configured")
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    if not _fernet:
        raise RuntimeError("CREDENTIAL_MASTER_KEY not configured")
    return _fernet.decrypt(ciphertext.encode()).decode()


def mask(plaintext: str) -> str:
    """Return masked version: last 4 chars visible, rest replaced with dots."""
    if not plaintext:
        return ""
    if len(plaintext) <= 4:
        return "****"
    return "****" + plaintext[-4:]
