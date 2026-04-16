# RED → GREEN
# Testes para encrypt_value / decrypt_value em app/core/security.py
import pytest
from cryptography.fernet import InvalidToken

from app.core.security import decrypt_value, encrypt_value


def test_encrypt_value_produces_different_string_from_plaintext() -> None:
    plain = "super-secret-master-key"
    cipher = encrypt_value(plain)
    assert cipher != plain
    assert len(cipher) > len(plain)


def test_decrypt_value_returns_original_plaintext() -> None:
    plain = "api-master-key-12345"
    cipher = encrypt_value(plain)
    assert decrypt_value(cipher) == plain


def test_encrypt_twice_produces_different_ciphertexts() -> None:
    plain = "same-input"
    c1 = encrypt_value(plain)
    c2 = encrypt_value(plain)
    assert c1 != c2
    assert decrypt_value(c1) == plain
    assert decrypt_value(c2) == plain


def test_decrypt_invalid_token_raises() -> None:
    with pytest.raises(InvalidToken):
        decrypt_value("not-a-valid-fernet-token")


def test_encrypt_decrypt_roundtrip_unicode() -> None:
    plain = "senha-com-acentuação-ç-ã-é"
    assert decrypt_value(encrypt_value(plain)) == plain
