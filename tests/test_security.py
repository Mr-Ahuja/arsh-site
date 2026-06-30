import time

import jwt
import pytest
from argon2 import PasswordHasher
from fastapi import Request

from core.errors import AuthError
from core.security import current_user, issue_jwt, verify_password


def _request_with_cookie(token: str | None) -> Request:
    headers = []
    if token is not None:
        headers.append((b"cookie", f"session={token}".encode()))
    scope = {"type": "http", "headers": headers}
    return Request(scope)


def test_verify_password_true_false():
    h = PasswordHasher().hash("hunter2")
    assert verify_password(h, "hunter2") is True
    assert verify_password(h, "wrong") is False
    assert verify_password("not-a-hash", "x") is False


def test_jwt_roundtrip():
    secret = "test-secret-key-for-tests"
    token = issue_jwt("mrahuja", secret)
    assert current_user(_request_with_cookie(token)) == "mrahuja"


def test_missing_token_raises():
    with pytest.raises(AuthError):
        current_user(_request_with_cookie(None))


def test_invalid_token_raises():
    with pytest.raises(AuthError):
        current_user(_request_with_cookie("garbage.token.value"))


def test_expired_token_raises():
    secret = "test-secret-key-for-tests"
    now = int(time.time())
    token = jwt.encode(
        {"sub": "mrahuja", "iat": now - 100, "exp": now - 10}, secret, algorithm="HS256"
    )
    with pytest.raises(AuthError):
        current_user(_request_with_cookie(token))
