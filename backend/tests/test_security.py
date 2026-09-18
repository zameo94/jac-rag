from datetime import timedelta

import jwt
import pytest

from app.core import security
from app.core.config import get_settings


def test_hash_password_is_verifiable():
    hashed = security.hash_password("supersecret")

    assert hashed != "supersecret"
    assert security.verify_password("supersecret", hashed) is True


def test_verify_password_fails_for_wrong_password():
    hashed = security.hash_password("supersecret")

    assert security.verify_password("wrong-password", hashed) is False


def test_hash_password_is_salted():
    assert security.hash_password("same-password") != security.hash_password("same-password")


def test_long_password_is_handled():
    long_password = "a" * 200

    hashed = security.hash_password(long_password)

    assert security.verify_password(long_password, hashed) is True


def test_access_token_round_trip():
    token = security.create_access_token(42)

    assert security.decode_token(token, security.ACCESS_TOKEN_TYPE) == 42


def test_refresh_token_round_trip():
    token = security.create_refresh_token(7)

    assert security.decode_token(token, security.REFRESH_TOKEN_TYPE) == 7


def test_decode_token_rejects_wrong_type():
    token = security.create_access_token(1)

    with pytest.raises(security.TokenError):
        security.decode_token(token, security.REFRESH_TOKEN_TYPE)


def test_decode_token_rejects_expired_token():
    token = security.create_access_token(1, expires_delta=timedelta(seconds=-1))

    with pytest.raises(security.TokenError):
        security.decode_token(token, security.ACCESS_TOKEN_TYPE)


def test_decode_token_rejects_tampered_token():
    token = security.create_access_token(1)

    with pytest.raises(security.TokenError):
        security.decode_token(f"{token}x", security.ACCESS_TOKEN_TYPE)


def test_decode_token_rejects_garbage():
    with pytest.raises(security.TokenError):
        security.decode_token("not-a-token", security.ACCESS_TOKEN_TYPE)


def test_decode_token_rejects_missing_subject():
    settings = get_settings()
    token = jwt.encode(
        {"type": security.ACCESS_TOKEN_TYPE},
        settings.jwt_secret,
        algorithm=security.JWT_ALGORITHM,
    )

    with pytest.raises(security.TokenError):
        security.decode_token(token, security.ACCESS_TOKEN_TYPE)


def test_decode_token_rejects_non_numeric_subject():
    settings = get_settings()
    token = jwt.encode(
        {"sub": "abc", "type": security.ACCESS_TOKEN_TYPE},
        settings.jwt_secret,
        algorithm=security.JWT_ALGORITHM,
    )

    with pytest.raises(security.TokenError):
        security.decode_token(token, security.ACCESS_TOKEN_TYPE)
