import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.core import security
from app.core.deps import get_embed_tenant, resolve_embed_tenant
from app.models import ApiKey, Membership
from app.schemas.membership import MembershipRole
from tests.helpers import register_and_login, user_id_for


async def create_tenant(client, headers, name: str = "Acme") -> int:
    response = await client.post("/api/v1/tenants", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def add_key(
    session_factory,
    tenant_id: int,
    user_id: int,
    *,
    active: bool = True,
    plaintext: str | None = None,
) -> tuple[ApiKey, str]:
    plaintext = plaintext or security.generate_embed_key()
    async with session_factory() as session:
        key = ApiKey(
            tenant_id=tenant_id,
            name="Widget",
            prefix=security.embed_key_prefix(plaintext),
            key_hash=security.hash_token(plaintext),
            created_by=user_id,
            is_active=active,
        )
        session.add(key)
        await session.commit()
        await session.refresh(key)
        return key, plaintext


async def add_member(session_factory, user_id: int, tenant_id: int) -> None:
    async with session_factory() as session:
        session.add(
            Membership(
                user_id=user_id, tenant_id=tenant_id, role=MembershipRole.MEMBER
            )
        )
        await session.commit()


def test_generate_embed_key_has_prefix():
    key = security.generate_embed_key()

    assert key.startswith("jrk_")
    assert security.embed_key_prefix(key) == key[:12]


async def test_create_api_key_returns_plaintext_once(client, session_factory):
    headers = await register_and_login(client, "keys-owner@example.com")
    tenant_id = await create_tenant(client, headers)

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/api-keys",
        json={"name": "Sito"},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Sito"
    assert body["key"].startswith("jrk_")
    assert body["prefix"] == body["key"][:12]
    assert body["is_active"] is True
    assert "key_hash" not in body

    async with session_factory() as session:
        stored = (await session.exec(select(ApiKey))).one()
    assert stored.key_hash == security.hash_token(body["key"])
    assert stored.key_hash != body["key"]


async def test_list_api_keys_hides_secret(client):
    headers = await register_and_login(client, "keys-list@example.com")
    tenant_id = await create_tenant(client, headers)
    await client.post(
        f"/api/v1/tenants/{tenant_id}/api-keys", json={"name": "A"}, headers=headers
    )
    await client.post(
        f"/api/v1/tenants/{tenant_id}/api-keys", json={"name": "B"}, headers=headers
    )

    response = await client.get(
        f"/api/v1/tenants/{tenant_id}/api-keys", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert [key["name"] for key in body] == ["B", "A"]
    assert all("key" not in key and "key_hash" not in key for key in body)


async def test_api_keys_require_manager_role(client, session_factory):
    owner_headers = await register_and_login(client, "keys-manager@example.com")
    tenant_id = await create_tenant(client, owner_headers)

    member_headers = await register_and_login(client, "keys-member@example.com")
    member_id = await user_id_for(client, member_headers)
    await add_member(session_factory, member_id, tenant_id)

    created = await client.post(
        f"/api/v1/tenants/{tenant_id}/api-keys",
        json={"name": "Nope"},
        headers=member_headers,
    )
    listed = await client.get(
        f"/api/v1/tenants/{tenant_id}/api-keys", headers=member_headers
    )

    assert created.status_code == 403
    assert created.json()["code"] == "INSUFFICIENT_ROLE"
    assert listed.status_code == 403


async def test_api_keys_reject_non_member_and_anonymous(client):
    owner_headers = await register_and_login(client, "keys-owner2@example.com")
    tenant_id = await create_tenant(client, owner_headers)
    other_headers = await register_and_login(client, "keys-other@example.com")

    other = await client.get(
        f"/api/v1/tenants/{tenant_id}/api-keys", headers=other_headers
    )
    client.cookies.clear()
    anonymous = await client.get(f"/api/v1/tenants/{tenant_id}/api-keys")

    assert other.status_code == 403
    assert other.json()["code"] == "NOT_A_MEMBER"
    assert anonymous.status_code == 401


async def test_update_api_key_toggles_active(client):
    headers = await register_and_login(client, "keys-toggle@example.com")
    tenant_id = await create_tenant(client, headers)
    created = await client.post(
        f"/api/v1/tenants/{tenant_id}/api-keys", json={"name": "T"}, headers=headers
    )
    key_id = created.json()["id"]

    disabled = await client.patch(
        f"/api/v1/tenants/{tenant_id}/api-keys/{key_id}",
        json={"is_active": False},
        headers=headers,
    )
    enabled = await client.patch(
        f"/api/v1/tenants/{tenant_id}/api-keys/{key_id}",
        json={"is_active": True},
        headers=headers,
    )

    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False
    assert enabled.json()["is_active"] is True


async def test_update_api_key_scoped_to_tenant(client):
    first = await register_and_login(client, "keys-first@example.com")
    first_tenant = await create_tenant(client, first, name="First Co")
    key_id = (
        await client.post(
            f"/api/v1/tenants/{first_tenant}/api-keys",
            json={"name": "First"},
            headers=first,
        )
    ).json()["id"]

    second = await register_and_login(client, "keys-second@example.com")
    second_tenant = await create_tenant(client, second, name="Second Co")

    response = await client.patch(
        f"/api/v1/tenants/{second_tenant}/api-keys/{key_id}",
        json={"is_active": False},
        headers=second,
    )

    assert response.status_code == 404
    assert response.json()["code"] == "API_KEY_NOT_FOUND"


async def test_resolve_embed_tenant_valid_updates_last_used(client, session_factory):
    headers = await register_and_login(client, "embed-owner@example.com")
    owner_id = await user_id_for(client, headers)
    tenant_id = await create_tenant(client, headers)
    key, plaintext = await add_key(session_factory, tenant_id, owner_id)

    async with session_factory() as session:
        tenant = await resolve_embed_tenant(session, plaintext)

    assert tenant.id == tenant_id

    async with session_factory() as session:
        stored = await session.get(ApiKey, key.id)
    assert stored.last_used_at is not None


async def test_get_embed_tenant_reads_header(client, session_factory):
    headers = await register_and_login(client, "embed-header@example.com")
    owner_id = await user_id_for(client, headers)
    tenant_id = await create_tenant(client, headers)
    _, plaintext = await add_key(session_factory, tenant_id, owner_id)

    async with session_factory() as session:
        tenant = await get_embed_tenant(plaintext, session)

    assert tenant.id == tenant_id


async def test_resolve_embed_tenant_missing(session_factory):
    async with session_factory() as session:
        with pytest.raises(HTTPException) as exc:
            await resolve_embed_tenant(session, None)

    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "EMBED_KEY_REQUIRED"


async def test_resolve_embed_tenant_invalid(session_factory):
    async with session_factory() as session:
        with pytest.raises(HTTPException) as exc:
            await resolve_embed_tenant(session, "jrk_not-a-real-key")

    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "INVALID_EMBED_KEY"


async def test_resolve_embed_tenant_disabled(client, session_factory):
    headers = await register_and_login(client, "embed-disabled@example.com")
    owner_id = await user_id_for(client, headers)
    tenant_id = await create_tenant(client, headers)
    _, plaintext = await add_key(session_factory, tenant_id, owner_id, active=False)

    async with session_factory() as session:
        with pytest.raises(HTTPException) as exc:
            await resolve_embed_tenant(session, plaintext)

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "EMBED_KEY_DISABLED"
