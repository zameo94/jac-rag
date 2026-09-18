from sqlmodel import select

from app.core import security
from app.models import User

REGISTER = {"email": "user@example.com", "password": "supersecret"}
REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
ME_URL = "/api/v1/auth/me"


async def do_register(client, **overrides):
    return await client.post(REGISTER_URL, json={**REGISTER, **overrides})


async def do_login(client, **overrides):
    payload = {"email": REGISTER["email"], "password": REGISTER["password"], **overrides}
    return await client.post(LOGIN_URL, json=payload)


async def access_token(client) -> str:
    return (await do_login(client)).json()["access_token"]


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


async def test_login_returns_token_pair(client):
    await do_register(client)

    response = await do_login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert security.decode_token(body["access_token"], security.ACCESS_TOKEN_TYPE)
    assert security.decode_token(body["refresh_token"], security.REFRESH_TOKEN_TYPE)


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


async def test_me_returns_current_user(client):
    await do_register(client)
    token = await access_token(client)

    response = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == REGISTER["email"]


async def test_me_rejects_invalid_token(client):
    response = await client.get(ME_URL, headers={"Authorization": "Bearer not-a-token"})

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


async def test_me_rejects_refresh_token(client):
    await do_register(client)
    refresh_token = (await do_login(client)).json()["refresh_token"]

    response = await client.get(ME_URL, headers={"Authorization": f"Bearer {refresh_token}"})

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


async def test_me_rejects_disabled_user(client, session_factory):
    await do_register(client)
    token = await access_token(client)
    await deactivate(session_factory, REGISTER["email"])

    response = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DISABLED"


async def test_login_rejects_disabled_user(client, session_factory):
    await do_register(client)
    await deactivate(session_factory, REGISTER["email"])

    response = await do_login(client)

    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DISABLED"


async def test_refresh_returns_new_token_pair(client):
    await do_register(client)
    refresh_token = (await do_login(client)).json()["refresh_token"]

    response = await client.post(REFRESH_URL, json={"refresh_token": refresh_token})

    assert response.status_code == 200
    body = response.json()
    assert security.decode_token(body["access_token"], security.ACCESS_TOKEN_TYPE)
    assert security.decode_token(body["refresh_token"], security.REFRESH_TOKEN_TYPE)


async def test_refresh_rejects_access_token(client):
    await do_register(client)
    token = await access_token(client)

    response = await client.post(REFRESH_URL, json={"refresh_token": token})

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_REFRESH_TOKEN"


async def test_refresh_rejects_garbage_token(client):
    response = await client.post(REFRESH_URL, json={"refresh_token": "garbage"})

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_REFRESH_TOKEN"


async def deactivate(session_factory, email: str) -> None:
    async with session_factory() as session:
        user = (await session.exec(select(User).where(User.email == email))).one()
        user.is_active = False
        session.add(user)
        await session.commit()
