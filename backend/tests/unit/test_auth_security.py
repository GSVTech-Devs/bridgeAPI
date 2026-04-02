# RED → GREEN
# Testes para app/core/security.py — funções puras, sem banco de dados.
from datetime import timedelta

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_not_plain_text() -> None:
    hashed = hash_password("mysecretpassword")
    assert hashed != "mysecretpassword"
    assert len(hashed) > 20


def test_hashed_password_verifies_correctly() -> None:
    hashed = hash_password("mysecretpassword")
    assert verify_password("mysecretpassword", hashed) is True


def test_wrong_password_does_not_verify() -> None:
    hashed = hash_password("mysecretpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_two_hashes_of_same_password_are_different() -> None:
    h1 = hash_password("samepassword")
    h2 = hash_password("samepassword")
    assert h1 != h2


def test_create_access_token_returns_string() -> None:
    token = create_access_token("user@example.com")
    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_access_token_returns_correct_subject() -> None:
    token = create_access_token("user@example.com")
    payload = decode_access_token(token)
    assert payload["sub"] == "user@example.com"


def test_expired_token_raises_jwt_error() -> None:
    token = create_access_token("user@example.com", expires_delta=timedelta(seconds=-1))
    with pytest.raises(JWTError):
        decode_access_token(token)


def test_tampered_token_raises_jwt_error() -> None:
    token = create_access_token("user@example.com")
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(JWTError):
        decode_access_token(tampered)
