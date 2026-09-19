from sqlmodel import select

from app.models import Membership
from app.schemas.membership import MembershipRole
from tests.helpers import register_and_login as auth_headers

TENANTS_URL = "/api/v1/tenants"


async def create_tenant(client, headers, **overrides):
    payload = {"name": "Acme", "slug": "acme", **overrides}
    return await client.post(TENANTS_URL, json=payload, headers=headers)


async def test_create_tenant_returns_created_tenant(client):
    headers = await auth_headers(client, "owner@example.com")

    response = await create_tenant(client, headers)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme"
    assert body["slug"] == "acme"
    assert body["default_locale"] == "it"
    assert body["answer_mode"] == "strict"
    assert isinstance(body["id"], int)


async def test_create_tenant_derives_slug_from_name(client):
    headers = await auth_headers(client, "owner@example.com")

    response = await create_tenant(client, headers, name="My Company!!", slug=None)

    assert response.status_code == 201
    assert response.json()["slug"] == "my-company"


async def test_create_tenant_accepts_assistive_mode(client):
    headers = await auth_headers(client, "owner@example.com")

    response = await create_tenant(client, headers, answer_mode="assistive")

    assert response.status_code == 201
    assert response.json()["answer_mode"] == "assistive"


async def test_create_tenant_assigns_owner_membership(client, session_factory):
    headers = await auth_headers(client, "owner@example.com")
    me = await client.get("/api/v1/auth/me", headers=headers)
    tenant = await create_tenant(client, headers)

    async with session_factory() as session:
        membership = (
            await session.exec(
                select(Membership).where(Membership.tenant_id == tenant.json()["id"])
            )
        ).one()

    assert membership.user_id == me.json()["id"]
    assert membership.role is MembershipRole.OWNER


async def test_create_tenant_rejects_duplicate_slug(client):
    headers = await auth_headers(client, "owner@example.com")
    await create_tenant(client, headers)

    response = await create_tenant(client, headers)

    assert response.status_code == 409
    assert response.json()["code"] == "SLUG_ALREADY_TAKEN"


async def test_create_tenant_requires_authentication(client):
    response = await client.post(TENANTS_URL, json={"name": "Acme", "slug": "acme"})

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_create_tenant_rejects_blank_name(client):
    headers = await auth_headers(client, "owner@example.com")

    response = await create_tenant(client, headers, name="   ")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_list_tenants_returns_only_memberships(client):
    owner_headers = await auth_headers(client, "owner@example.com")
    other_headers = await auth_headers(client, "other@example.com")

    await create_tenant(client, owner_headers, name="Acme", slug="acme")
    await create_tenant(client, owner_headers, name="Beta", slug="beta")
    await create_tenant(client, other_headers, name="Gamma", slug="gamma")

    owner_list = await client.get(TENANTS_URL, headers=owner_headers)
    other_list = await client.get(TENANTS_URL, headers=other_headers)

    assert [tenant["slug"] for tenant in owner_list.json()] == ["acme", "beta"]
    assert [tenant["slug"] for tenant in other_list.json()] == ["gamma"]


async def test_list_tenants_requires_authentication(client):
    response = await client.get(TENANTS_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_get_tenant_as_member(client):
    headers = await auth_headers(client, "owner@example.com")
    tenant = await create_tenant(client, headers)

    response = await client.get(f"{TENANTS_URL}/{tenant.json()['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["slug"] == "acme"


async def test_get_tenant_as_non_member_returns_403(client):
    owner_headers = await auth_headers(client, "owner@example.com")
    other_headers = await auth_headers(client, "other@example.com")
    tenant = await create_tenant(client, owner_headers)

    response = await client.get(
        f"{TENANTS_URL}/{tenant.json()['id']}", headers=other_headers
    )

    assert response.status_code == 403
    assert response.json()["code"] == "NOT_A_MEMBER"


async def test_get_tenant_not_found_returns_404(client):
    headers = await auth_headers(client, "owner@example.com")

    response = await client.get(f"{TENANTS_URL}/999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["code"] == "TENANT_NOT_FOUND"


async def test_get_tenant_requires_authentication(client):
    owner_headers = await auth_headers(client, "owner@example.com")
    tenant = await create_tenant(client, owner_headers)
    client.cookies.clear()

    response = await client.get(f"{TENANTS_URL}/{tenant.json()['id']}")

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"
