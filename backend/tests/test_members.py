from sqlmodel import select

from app.models import Membership
from app.schemas.membership import MembershipRole

AUTH_URL = "/api/v1/auth"
TENANTS_URL = "/api/v1/tenants"


async def register_and_login(client, email: str) -> dict[str, str]:
    await client.post(f"{AUTH_URL}/register", json={"email": email, "password": "supersecret"})
    response = await client.post(
        f"{AUTH_URL}/login", json={"email": email, "password": "supersecret"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create_tenant(client, headers, name="Acme", slug="acme"):
    response = await client.post(
        TENANTS_URL, json={"name": name, "slug": slug}, headers=headers
    )
    return response.json()


async def add_membership(session_factory, tenant_id, user_id, role):
    async with session_factory() as session:
        session.add(Membership(user_id=user_id, tenant_id=tenant_id, role=role))
        await session.commit()


async def user_id_for(client, headers) -> int:
    return (await client.get(f"{AUTH_URL}/me", headers=headers)).json()["id"]


async def test_list_members_includes_owner(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)

    response = await client.get(f"{TENANTS_URL}/{tenant['id']}/members", headers=owner)

    assert response.status_code == 200
    members = response.json()
    assert len(members) == 1
    assert members[0]["email"] == "owner@example.com"
    assert members[0]["role"] == "OWNER"


async def test_list_members_requires_membership(client):
    owner = await register_and_login(client, "owner@example.com")
    outsider = await register_and_login(client, "outsider@example.com")
    tenant = await create_tenant(client, owner)

    response = await client.get(f"{TENANTS_URL}/{tenant['id']}/members", headers=outsider)

    assert response.status_code == 403
    assert response.json()["code"] == "NOT_A_MEMBER"


async def test_list_members_requires_authentication(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)

    response = await client.get(f"{TENANTS_URL}/{tenant['id']}/members")

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_admin_can_promote_member(client, session_factory):
    owner = await register_and_login(client, "owner@example.com")
    admin = await register_and_login(client, "admin@example.com")
    tenant = await create_tenant(client, owner)
    admin_id = await user_id_for(client, admin)
    await add_membership(session_factory, tenant["id"], admin_id, MembershipRole.ADMIN)

    target = await register_and_login(client, "member@example.com")
    target_id = await user_id_for(client, target)
    await add_membership(session_factory, tenant["id"], target_id, MembershipRole.MEMBER)

    response = await client.patch(
        f"{TENANTS_URL}/{tenant['id']}/members/{target_id}",
        json={"role": "ADMIN"},
        headers=admin,
    )

    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"


async def test_member_cannot_change_roles(client, session_factory):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    member = await register_and_login(client, "member@example.com")
    member_id = await user_id_for(client, member)
    await add_membership(session_factory, tenant["id"], member_id, MembershipRole.MEMBER)

    response = await client.patch(
        f"{TENANTS_URL}/{tenant['id']}/members/{member_id}",
        json={"role": "ADMIN"},
        headers=member,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


async def test_cannot_change_owner_role(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    owner_id = await user_id_for(client, owner)

    response = await client.patch(
        f"{TENANTS_URL}/{tenant['id']}/members/{owner_id}",
        json={"role": "ADMIN"},
        headers=owner,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "CANNOT_MODIFY_OWNER"


async def test_cannot_assign_owner_role(client, session_factory):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    member = await register_and_login(client, "member@example.com")
    member_id = await user_id_for(client, member)
    await add_membership(session_factory, tenant["id"], member_id, MembershipRole.MEMBER)

    response = await client.patch(
        f"{TENANTS_URL}/{tenant['id']}/members/{member_id}",
        json={"role": "OWNER"},
        headers=owner,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_update_unknown_member_returns_404(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)

    response = await client.patch(
        f"{TENANTS_URL}/{tenant['id']}/members/999999",
        json={"role": "ADMIN"},
        headers=owner,
    )

    assert response.status_code == 404
    assert response.json()["code"] == "MEMBER_NOT_FOUND"


async def test_admin_can_remove_member(client, session_factory):
    owner = await register_and_login(client, "owner@example.com")
    admin = await register_and_login(client, "admin@example.com")
    tenant = await create_tenant(client, owner)
    admin_id = await user_id_for(client, admin)
    await add_membership(session_factory, tenant["id"], admin_id, MembershipRole.ADMIN)

    target = await register_and_login(client, "member@example.com")
    target_id = await user_id_for(client, target)
    await add_membership(session_factory, tenant["id"], target_id, MembershipRole.MEMBER)

    response = await client.delete(
        f"{TENANTS_URL}/{tenant['id']}/members/{target_id}", headers=admin
    )

    assert response.status_code == 204

    async with session_factory() as session:
        remaining = (
            await session.exec(
                select(Membership).where(Membership.user_id == target_id)
            )
        ).all()
    assert remaining == []


async def test_member_cannot_remove_others(client, session_factory):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    member = await register_and_login(client, "member@example.com")
    member_id = await user_id_for(client, member)
    await add_membership(session_factory, tenant["id"], member_id, MembershipRole.MEMBER)

    other = await register_and_login(client, "other@example.com")
    other_id = await user_id_for(client, other)
    await add_membership(session_factory, tenant["id"], other_id, MembershipRole.MEMBER)

    response = await client.delete(
        f"{TENANTS_URL}/{tenant['id']}/members/{other_id}", headers=member
    )

    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


async def test_cannot_remove_self(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    owner_id = await user_id_for(client, owner)

    response = await client.delete(
        f"{TENANTS_URL}/{tenant['id']}/members/{owner_id}", headers=owner
    )

    assert response.status_code == 403
    assert response.json()["code"] == "CANNOT_REMOVE_SELF"


async def test_cannot_remove_owner(client, session_factory):
    owner = await register_and_login(client, "owner@example.com")
    admin = await register_and_login(client, "admin@example.com")
    tenant = await create_tenant(client, owner)
    owner_id = await user_id_for(client, owner)
    admin_id = await user_id_for(client, admin)
    await add_membership(session_factory, tenant["id"], admin_id, MembershipRole.ADMIN)

    response = await client.delete(
        f"{TENANTS_URL}/{tenant['id']}/members/{owner_id}", headers=admin
    )

    assert response.status_code == 403
    assert response.json()["code"] == "CANNOT_REMOVE_OWNER"


async def test_remove_unknown_member_returns_404(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)

    response = await client.delete(
        f"{TENANTS_URL}/{tenant['id']}/members/999999", headers=owner
    )

    assert response.status_code == 404
    assert response.json()["code"] == "MEMBER_NOT_FOUND"


async def test_remove_member_from_other_tenant_returns_404(client, session_factory):
    owner_a = await register_and_login(client, "owner-a@example.com")
    tenant_a = await create_tenant(client, owner_a, name="Alpha", slug="alpha")
    owner_b = await register_and_login(client, "owner-b@example.com")
    tenant_b = await create_tenant(client, owner_b, name="Beta", slug="beta")

    victim = await register_and_login(client, "victim@example.com")
    victim_id = await user_id_for(client, victim)
    await add_membership(session_factory, tenant_a["id"], victim_id, MembershipRole.MEMBER)

    response = await client.delete(
        f"{TENANTS_URL}/{tenant_b['id']}/members/{victim_id}", headers=owner_b
    )

    assert response.status_code == 404
    assert response.json()["code"] == "MEMBER_NOT_FOUND"
