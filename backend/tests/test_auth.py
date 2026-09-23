from sqlmodel import select

from app.core import security
from app.models import User

REGISTER = {"email": "user@example.com", "password": "supersecret"}
REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/auth/me"

ACCESS_COOKIE = "jacrag_access"
REFRESH_COOKIE = "jacrag_refresh"


async def do_register(client, **overrides):
    return await client.post(REGISTER_URL, json={**REGISTER, **overrides})


async def do_login(client, **overrides):
    payload = {"email": REGISTER["email"], "password": REGISTER["password"], **overrides}
    return await client.post(LOGIN_URL, json=payload)


async def access_token(client) -> str:
    await do_login(client)
    return client.cookies.get(ACCESS_COOKIE)


async def get_user(session_factory, email):
    async with session_factory() as session:
        return (await session.exec(select(User).where(User.email == email))).one()


async def test_register_creates_user(client):
    response = await do_register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "user@example.com"
    assert body["locale"] == "it"
    assert body["is_active"] is True
    assert isinstance(body["id"], int)
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_normalizes_email(client):
    response = await do_register(client, email="  Mixed@Case.IT ")

    assert response.status_code == 201
    assert response.json()["email"] == "mixed@case.it"


async def test_register_accepts_english_locale(client):
    response = await do_register(client, locale="en")

    assert response.status_code == 201
    assert response.json()["locale"] == "en"


async def test_register_hashes_password(client, session_factory):
    await do_register(client)

    user = await get_user(session_factory, REGISTER["email"])

    assert user.password_hash != REGISTER["password"]
    assert security.verify_password(REGISTER["password"], user.password_hash)


async def test_register_duplicate_email_returns_409(client):
    await do_register(client)

    response = await do_register(client)

    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_register_invalid_email_returns_422(client):
    response = await do_register(client, email="not-an-email")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["details"]


async def test_register_short_password_returns_422(client):
    response = await do_register(client, password="short")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_register_unsupported_locale_returns_422(client):
    response = await do_register(client, locale="fr")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_login_sets_http_only_cookies(client):
    await do_register(client)

    response = await do_login(client)

    assert response.status_code == 200
    assert response.json()["email"] == REGISTER["email"]
    set_cookie = response.headers.get_list("set-cookie")
    assert any(ACCESS_COOKIE in cookie and "HttpOnly" in cookie for cookie in set_cookie)
    assert any(REFRESH_COOKIE in cookie and "HttpOnly" in cookie for cookie in set_cookie)


async def test_login_does_not_return_tokens_in_body(client):
    await do_register(client)

    body = (await do_login(client)).json()

    assert "access_token" not in body
    assert "refresh_token" not in body


async def test_login_is_case_insensitive_on_email(client):
    await do_register(client, email="user@example.com")

    response = await do_login(client, email="  USER@Example.com ")

    assert response.status_code == 200


async def test_login_wrong_password_returns_401(client):
    await do_register(client)

    response = await do_login(client, password="wrong-password")

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


async def test_login_unknown_email_returns_401(client):
    response = await do_login(client)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


async def test_me_requires_authentication(client):
    response = await client.get(ME_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_me_returns_current_user_with_cookie(client):
    await do_register(client)
    await do_login(client)

    response = await client.get(ME_URL)

    assert response.status_code == 200
    assert response.json()["email"] == REGISTER["email"]


async def test_me_accepts_bearer_token(client):
    await do_register(client)
    token = await access_token(client)

    response = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == REGISTER["email"]


async def test_me_rejects_invalid_bearer_token(client):
    response = await client.get(ME_URL, headers={"Authorization": "Bearer not-a-token"})

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


async def test_me_rejects_refresh_cookie_as_access(client):
    await do_register(client)
    await do_login(client)
    refresh_token = client.cookies.get(REFRESH_COOKIE)

    response = await client.get(
        ME_URL, headers={"Authorization": f"Bearer {refresh_token}"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


async def test_me_rejects_disabled_user(client, session_factory):
    await do_register(client)
    await do_login(client)
    await deactivate(session_factory, REGISTER["email"])

    response = await client.get(ME_URL)

    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DISABLED"


async def test_login_rejects_disabled_user(client, session_factory):
    await do_register(client)
    await deactivate(session_factory, REGISTER["email"])

    response = await do_login(client)

    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DISABLED"


async def test_refresh_rotates_cookies(client):
    await do_register(client)
    await do_login(client)
    previous = client.cookies.get(ACCESS_COOKIE)

    response = await client.post(REFRESH_URL)

    assert response.status_code == 200
    assert client.cookies.get(ACCESS_COOKIE)
    assert client.cookies.get(ACCESS_COOKIE) != previous
    me = await client.get(ME_URL)
    assert me.status_code == 200


async def test_refresh_without_cookie_returns_401(client):
    await do_register(client)

    response = await client.post(REFRESH_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_REFRESH_TOKEN"


async def test_refresh_rejects_access_token_in_refresh_cookie(client):
    await do_register(client)
    await do_login(client)
    access_token_value = client.cookies.get(ACCESS_COOKIE)
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, access_token_value, path="/")

    response = await client.post(REFRESH_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_REFRESH_TOKEN"


async def test_refresh_rejects_garbage_cookie(client):
    client.cookies.set(REFRESH_COOKIE, "garbage", path="/api/v1/auth")

    response = await client.post(REFRESH_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_REFRESH_TOKEN"


async def test_logout_clears_cookies(client):
    await do_register(client)
    await do_login(client)

    response = await client.post(LOGOUT_URL)

    assert response.status_code == 204
    assert client.cookies.get(ACCESS_COOKIE) is None
    assert client.cookies.get(REFRESH_COOKIE) is None
    assert (await client.get(ME_URL)).status_code == 401


async def test_register_blocked_by_rate_limit(client, monkeypatch):
    from app.api.v1 import auth as auth_module

    called = {}

    async def denied(scope, ip, email=None):
        called["scope"] = scope
        called["email"] = email
        return False

    monkeypatch.setattr(auth_module, "auth_allowed", denied)

    response = await do_register(client)

    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"
    assert called == {"scope": "register", "email": "user@example.com"}


async def test_login_blocked_by_rate_limit(client, monkeypatch):
    from app.api.v1 import auth as auth_module

    async def denied(scope, ip, email=None):
        return False

    monkeypatch.setattr(auth_module, "auth_allowed", denied)

    response = await do_login(client)

    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"


async def test_refresh_blocked_by_rate_limit(client, monkeypatch):
    from app.api.v1 import auth as auth_module

    called = {}

    async def denied(scope, ip, email=None):
        called["scope"] = scope
        called["email"] = email
        return False

    monkeypatch.setattr(auth_module, "auth_allowed", denied)

    response = await client.post(REFRESH_URL)

    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"
    assert called == {"scope": "refresh", "email": None}


async def test_rate_limit_passed_does_not_block_request(client, monkeypatch):
    from app.api.v1 import auth as auth_module

    async def allowed(scope, ip, email=None):
        return True

    monkeypatch.setattr(auth_module, "auth_allowed", allowed)

    response = await do_register(client)

    assert response.status_code == 201


async def deactivate(session_factory, email: str) -> None:
    async with session_factory() as session:
        user = (await session.exec(select(User).where(User.email == email))).one()
        user.is_active = False
        session.add(user)
        await session.commit()


async def test_update_me_changes_locale(client):
    await do_register(client)
    await do_login(client)

    response = await client.patch(ME_URL, json={"locale": "en"})

    assert response.status_code == 200
    assert response.json()["locale"] == "en"


async def test_update_me_normalizes_locale(client):
    await do_register(client)
    await do_login(client)

    response = await client.patch(ME_URL, json={"locale": "EN"})

    assert response.status_code == 200
    assert response.json()["locale"] == "en"


async def test_update_me_persists_locale(client, session_factory):
    await do_register(client)
    await do_login(client)

    await client.patch(ME_URL, json={"locale": "en"})

    user = await get_user(session_factory, REGISTER["email"])
    assert user.locale == "en"


async def test_update_me_rejects_unsupported_locale(client):
    await do_register(client)
    await do_login(client)

    response = await client.patch(ME_URL, json={"locale": "fr"})

    assert response.status_code == 422


async def test_update_me_requires_authentication(client):
    response = await client.patch(ME_URL, json={"locale": "en"})

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"
