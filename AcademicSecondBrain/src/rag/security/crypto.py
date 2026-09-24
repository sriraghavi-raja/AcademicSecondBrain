"""Symmetric encryption for secrets we must store (e.g. a student's own GitHub token) but never
log, return to a client, or keep in plaintext at rest.
"""

import os

from cryptography.fernet import Fernet


class EncryptionKeyMissing(RuntimeError):
    """GITHUB_TOKEN_ENCRYPTION_KEY is not set."""


def _cipher() -> Fernet:
    key = os.getenv("GITHUB_TOKEN_ENCRYPTION_KEY")
    if not key:
        raise EncryptionKeyMissing("GITHUB_TOKEN_ENCRYPTION_KEY is not set")
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    return _cipher().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _cipher().decrypt(ciphertext.encode()).decode()
