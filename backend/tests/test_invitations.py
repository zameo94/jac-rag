from datetime import timedelta

from sqlmodel import select

from app.core import security
from app.core.datetimes import utcnow
from app.models import Invitation, Membership
from app.schemas.membership import MembershipRole
from tests.helpers import register_and_login, user_id_for

TENANTS_URL = "/api/v1/tenants"
INVITATIONS_URL = "/api/v1/invitations"


async def create_tenant(client, headers, name="Acme", slug="acme"):
    response = await client.post(
        TENANTS_URL, json={"name": name, "slug": slug}, headers=headers
    )
    return response.json()


async def invite(client, headers, tenant_id, email, role="MEMBER"):
    return await client.post(
        f"{TENANTS_URL}/{tenant_id}/invitations",
        json={"email": email, "role": role},
        headers=headers,
    )


async def test_owner_can_create_invitation(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)

    response = await invite(client, owner, tenant["id"], "Newbie@Example.com")

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newbie@example.com"
    assert body["role"] == "MEMBER"
    assert body["tenant_id"] == tenant["id"]
    assert isinstance(body["token"], str) and body["token"]
    assert "expires_at" in body


async def test_invitation_stores_only_token_hash(client, session_factory):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    response = await invite(client, owner, tenant["id"], "newbie@example.com")
    raw_token = response.json()["token"]

    async with session_factory() as session:
        invitation = (await session.exec(select(Invitation))).one()

    assert invitation.token_hash == security.hash_token(raw_token)
    assert invitation.token_hash != raw_token


async def test_admin_can_create_invitation(client, session_factory):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    admin = await register_and_login(client, "admin@example.com")
    admin_id = await user_id_for(client, admin)
    async with session_factory() as session:
        session.add(
            Membership(user_id=admin_id, tenant_id=tenant["id"], role=MembershipRole.ADMIN)
        )
        await session.commit()

    response = await invite(client, admin, tenant["id"], "newbie@example.com")

    assert response.status_code == 201


async def test_member_cannot_create_invitation(client, session_factory):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    member = await register_and_login(client, "member@example.com")
    member_id = await user_id_for(client, member)
    async with session_factory() as session:
        session.add(
            Membership(user_id=member_id, tenant_id=tenant["id"], role=MembershipRole.MEMBER)
        )
        await session.commit()

    response = await invite(client, member, tenant["id"], "newbie@example.com")

    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


async def test_non_member_cannot_create_invitation(client):
    owner = await register_and_login(client, "owner@example.com")
    outsider = await register_and_login(client, "outsider@example.com")
    tenant = await create_tenant(client, owner)

    response = await invite(client, outsider, tenant["id"], "newbie@example.com")

    assert response.status_code == 403
    assert response.json()["code"] == "NOT_A_MEMBER"


async def test_cannot_invite_existing_member(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)

    response = await invite(client, owner, tenant["id"], "owner@example.com")

    assert response.status_code == 409
    assert response.json()["code"] == "ALREADY_A_MEMBER"


async def test_cannot_invite_owner_role(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)

    response = await invite(client, owner, tenant["id"], "newbie@example.com", role="OWNER")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_duplicate_pending_invitation_returns_409(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    await invite(client, owner, tenant["id"], "newbie@example.com")

    response = await invite(client, owner, tenant["id"], "newbie@example.com")

    assert response.status_code == 409
    assert response.json()["code"] == "INVITATION_ALREADY_PENDING"


async def test_accept_invitation_creates_membership(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    token = (await invite(client, owner, tenant["id"], "newbie@example.com")).json()["token"]
    newbie = await register_and_login(client, "newbie@example.com")

    response = await client.post(f"{INVITATIONS_URL}/{token}/accept", headers=newbie)

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == tenant["id"]
    assert body["role"] == "MEMBER"

    listing = await client.get(TENANTS_URL, headers=newbie)
    assert [t["slug"] for t in listing.json()] == ["acme"]


async def test_accept_invitation_with_admin_role(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    token = (
        await invite(client, owner, tenant["id"], "newbie@example.com", role="ADMIN")
    ).json()["token"]
    newbie = await register_and_login(client, "newbie@example.com")

    response = await client.post(f"{INVITATIONS_URL}/{token}/accept", headers=newbie)

    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"


async def test_accept_invitation_marks_accepted(client, session_factory):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    token = (await invite(client, owner, tenant["id"], "newbie@example.com")).json()["token"]
    newbie = await register_and_login(client, "newbie@example.com")

    await client.post(f"{INVITATIONS_URL}/{token}/accept", headers=newbie)

    async with session_factory() as session:
        invitation = (await session.exec(select(Invitation))).one()

    assert invitation.accepted_at is not None


async def test_accept_invitation_twice_returns_409(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    token = (await invite(client, owner, tenant["id"], "newbie@example.com")).json()["token"]
    newbie = await register_and_login(client, "newbie@example.com")
    await client.post(f"{INVITATIONS_URL}/{token}/accept", headers=newbie)

    response = await client.post(f"{INVITATIONS_URL}/{token}/accept", headers=newbie)

    assert response.status_code == 409
    assert response.json()["code"] == "INVITATION_ALREADY_ACCEPTED"


async def test_accept_unknown_token_returns_404(client):
    newbie = await register_and_login(client, "newbie@example.com")

    response = await client.post(f"{INVITATIONS_URL}/does-not-exist/accept", headers=newbie)

    assert response.status_code == 404
    assert response.json()["code"] == "INVITATION_NOT_FOUND"


async def test_accept_invitation_requires_authentication(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    token = (await invite(client, owner, tenant["id"], "newbie@example.com")).json()["token"]
    client.cookies.clear()

    response = await client.post(f"{INVITATIONS_URL}/{token}/accept")

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_accept_invitation_for_other_email_returns_403(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    token = (await invite(client, owner, tenant["id"], "newbie@example.com")).json()["token"]
    stranger = await register_and_login(client, "stranger@example.com")

    response = await client.post(f"{INVITATIONS_URL}/{token}/accept", headers=stranger)

    assert response.status_code == 403
    assert response.json()["code"] == "INVITATION_EMAIL_MISMATCH"


async def test_accept_expired_invitation_returns_410(client, session_factory):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    token = (await invite(client, owner, tenant["id"], "newbie@example.com")).json()["token"]

    async with session_factory() as session:
        invitation = (await session.exec(select(Invitation))).one()
        invitation.expires_at = utcnow() - timedelta(days=1)
        session.add(invitation)
        await session.commit()

    newbie = await register_and_login(client, "newbie@example.com")
    response = await client.post(f"{INVITATIONS_URL}/{token}/accept", headers=newbie)

    assert response.status_code == 410
    assert response.json()["code"] == "INVITATION_EXPIRED"


async def test_accept_when_already_member_returns_409(client, session_factory):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    newbie = await register_and_login(client, "newbie@example.com")
    token = (await invite(client, owner, tenant["id"], "newbie@example.com")).json()["token"]
    newbie_id = await user_id_for(client, newbie)
    async with session_factory() as session:
        session.add(
            Membership(
                user_id=newbie_id, tenant_id=tenant["id"], role=MembershipRole.MEMBER
            )
        )
        await session.commit()

    response = await client.post(f"{INVITATIONS_URL}/{token}/accept", headers=newbie)

    assert response.status_code == 409
    assert response.json()["code"] == "ALREADY_A_MEMBER"


async def test_invitation_is_tenant_scoped(client):
    owner_a = await register_and_login(client, "owner-a@example.com")
    tenant_a = await create_tenant(client, owner_a, name="Alpha", slug="alpha")
    owner_b = await register_and_login(client, "owner-b@example.com")
    tenant_b = await create_tenant(client, owner_b, name="Beta", slug="beta")

    token_a = (await invite(client, owner_a, tenant_a["id"], "newbie@example.com")).json()[
        "token"
    ]
    newbie = await register_and_login(client, "newbie@example.com")

    response = await client.post(f"{INVITATIONS_URL}/{token_a}/accept", headers=newbie)

    assert response.status_code == 200
    assert response.json()["tenant_id"] == tenant_a["id"]
    assert response.json()["tenant_id"] != tenant_b["id"]
