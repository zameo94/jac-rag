from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core import security
from app.core.config import get_settings

REFRESH_COOKIE = "jacrag_refresh"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
REGISTER_URL = "/api/v1/auth/register"
REGISTER = {"email": "user@example.com", "password": "supersecret"}


def _payload(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False})


def _refresh_set_cookie(response) -> str:
    for cookie in response.headers.get_list("set-cookie"):
        if REFRESH_COOKIE in cookie:
            return cookie
    raise AssertionError("refresh cookie not set")


def _cookie_max_age(set_cookie: str) -> int:
    for part in set_cookie.split(";"):
        if part.strip().lower().startswith("max-age="):
            return int(part.strip().split("=", 1)[1])
    raise AssertionError("Max-Age missing from cookie")


def test_refresh_lifetime_uses_idle_timeout_when_shorter(monkeypatch):
    monkeypatch.setenv("SESSION_IDLE_TIMEOUT_MINUTES", "60")
    monkeypatch.setenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
    get_settings.cache_clear()

    lifetime = security.refresh_token_lifetime(datetime.now(timezone.utc))

    assert int(lifetime.total_seconds()) == 60 * 60


def test_refresh_lifetime_zero_idle_keeps_absolute_days(monkeypatch):
    monkeypatch.setenv("SESSION_IDLE_TIMEOUT_MINUTES", "0")
    monkeypatch.setenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
    get_settings.cache_clear()

    lifetime = security.refresh_token_lifetime(datetime.now(timezone.utc))

    assert int(lifetime.total_seconds()) == 7 * 24 * 60 * 60


def test_refresh_lifetime_bounded_by_absolute_ceiling(monkeypatch):
    monkeypatch.setenv("SESSION_IDLE_TIMEOUT_MINUTES", "10080")
    monkeypatch.setenv("REFRESH_TOKEN_EXPIRE_DAYS", "2")
    get_settings.cache_clear()

    lifetime = security.refresh_token_lifetime(datetime.now(timezone.utc))

    assert timedelta(days=2) - timedelta(seconds=10) <= lifetime <= timedelta(days=2)


def test_expired_refresh_token_is_rejected(monkeypatch):
    monkeypatch.setenv("SESSION_IDLE_TIMEOUT_MINUTES", "60")
    get_settings.cache_clear()

    expired = security.create_refresh_token(1, expires_delta=timedelta(seconds=-1))

    try:
        security.decode_token(expired, security.REFRESH_TOKEN_TYPE)
        raise AssertionError("expired token must be rejected")
    except security.TokenError:
        pass


async def test_login_sets_refresh_cookie_with_idle_max_age(client, monkeypatch):
    monkeypatch.setenv("SESSION_IDLE_TIMEOUT_MINUTES", "60")
    get_settings.cache_clear()
    await client.post("/api/v1/auth/register", json=REGISTER)

    response = await client.post(LOGIN_URL, json=REGISTER)

    assert response.status_code == 200
    set_cookie = _refresh_set_cookie(response)
    assert _cookie_max_age(set_cookie) == 60 * 60


async def test_refresh_token_exp_equals_now_plus_idle(client, monkeypatch):
    monkeypatch.setenv("SESSION_IDLE_TIMEOUT_MINUTES", "60")
    get_settings.cache_clear()
    await client.post("/api/v1/auth/register", json=REGISTER)

    await client.post(LOGIN_URL, json=REGISTER)
    token = client.cookies.get(REFRESH_COOKIE)

    payload = _payload(token)
    assert payload["exp"] - payload["iat"] == 60 * 60


async def test_refresh_slides_the_refresh_token_expiry(client, monkeypatch):
    monkeypatch.setenv("SESSION_IDLE_TIMEOUT_MINUTES", "60")
    get_settings.cache_clear()
    await client.post("/api/v1/auth/register", json=REGISTER)
    await client.post(LOGIN_URL, json=REGISTER)

    response = await client.post(REFRESH_URL)

    assert response.status_code == 200
    refreshed = client.cookies.get(REFRESH_COOKIE)
    payload = _payload(refreshed)
    assert payload["exp"] - payload["iat"] == 60 * 60


async def test_idle_disabled_keeps_refresh_cookie_in_days(client, monkeypatch):
    monkeypatch.setenv("SESSION_IDLE_TIMEOUT_MINUTES", "0")
    get_settings.cache_clear()
    await client.post("/api/v1/auth/register", json=REGISTER)

    response = await client.post(LOGIN_URL, json=REGISTER)

    set_cookie = _refresh_set_cookie(response)
    assert _cookie_max_age(set_cookie) == 7 * 24 * 60 * 60


def test_decode_refresh_token_returns_session_start():
    started = datetime.now(timezone.utc) - timedelta(hours=3)
    token = security.create_refresh_token(5, session_started_at=started)

    identity = security.decode_refresh_token(token)

    assert identity.user_id == 5
    assert identity.session_started_at.timestamp() == pytest.approx(
        started.timestamp(), abs=1
    )


def test_decode_refresh_token_falls_back_to_iat():
    token = security._create_token(5, security.REFRESH_TOKEN_TYPE, timedelta(days=1))

    identity = security.decode_refresh_token(token)

    assert identity.user_id == 5
    assert identity.session_started_at.tzinfo is not None


async def test_refresh_respects_absolute_ceiling(client, monkeypatch):
    monkeypatch.setenv("SESSION_IDLE_TIMEOUT_MINUTES", "10080")
    monkeypatch.setenv("REFRESH_TOKEN_EXPIRE_DAYS", "2")
    get_settings.cache_clear()
    created = await client.post(REGISTER_URL, json=REGISTER)
    user_id = created.json()["id"]

    started = datetime.now(timezone.utc) - timedelta(days=1)
    token = security.create_refresh_token(
        user_id, expires_delta=timedelta(days=1), session_started_at=started
    )

    response = await client.post(
        REFRESH_URL, headers={"cookie": f"{REFRESH_COOKIE}={token}"}
    )

    assert response.status_code == 200
    payload = _payload(client.cookies.get(REFRESH_COOKIE))
    assert payload["session_started_at"] == pytest.approx(started.timestamp(), abs=1)
    ceiling = started.timestamp() + 2 * 24 * 60 * 60
    assert payload["exp"] == pytest.approx(ceiling, abs=2)