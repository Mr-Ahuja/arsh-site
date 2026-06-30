"""Fernet symmetric encryption for secrets stored at rest (Kite token, api_secret).

The Fernet key is derived from APP_SECRET so no separate key file is needed.
"""

import base64
import hashlib

from cryptography.fernet import Fernet


def _key(secret: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


def encrypt(s: str, secret: str) -> str:
    return Fernet(_key(secret)).encrypt(s.encode()).decode()


def decrypt(s: str, secret: str) -> str:
    return Fernet(_key(secret)).decrypt(s.encode()).decode()
