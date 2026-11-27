# tests/test_security.py
import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-ci-only-32-bytes-long")

import pytest
from fastapi import HTTPException
from core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify():
    hashed = hash_password("Segura123!")
    assert hashed != "Segura123!"
    assert verify_password("Segura123!", hashed) is True
    assert verify_password("Incorrecta123!", hashed) is False


def test_password_rejects_short_and_over_72_bytes():
    with pytest.raises(HTTPException) as short_err:
        hash_password("1234567")
    assert short_err.value.status_code == 400

    with pytest.raises(HTTPException) as long_err:
        hash_password("a" * 73)
    assert long_err.value.status_code == 400


def test_jwt_create_and_decode():
    token = create_access_token({"sub": "admin@test.com", "role": "admin"})
    payload = decode_access_token(token)
    assert payload["sub"] == "admin@test.com"
    assert payload["role"] == "admin"
    assert "exp" in payload


def test_jwt_invalid_token_raises_401():
    with pytest.raises(HTTPException) as exc:
        decode_access_token("token-invalido")
    assert exc.value.status_code == 401