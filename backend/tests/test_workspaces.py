from sqlmodel import select

from app.models import Membership
from app.schemas.membership import MembershipRole
from tests.helpers import register_and_login as auth_headers, user_id_for

WORKSPACES_URL = "/api/v1/workspaces"


async def create_workspace(client, headers, **overrides):
    payload = {"name": "Acme", "slug": "acme", **overrides}
    return await client.post(WORKSPACES_URL, json=payload, headers=headers)


async def test_create_workspace_returns_created_workspace(client):
    headers = await auth_headers(client, "owner@example.com")

    response = await create_workspace(client, headers)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme"
    assert body["slug"] == "acme"
    assert body["default_locale"] == "it"
    assert body["answer_mode"] == "strict"
    assert body["is_active"] is True
    assert isinstance(body["id"], int)


async def test_create_workspace_derives_slug_from_name(client):
    headers = await auth_headers(client, "owner@example.com")

    response = await create_workspace(client, headers, name="My Company!!", slug=None)

    assert response.status_code == 201
    assert response.json()["slug"] == "my-company"


async def test_create_workspace_accepts_assistive_mode(client):
    headers = await auth_headers(client, "owner@example.com")

    response = await create_workspace(client, headers, answer_mode="assistive")

    assert response.status_code == 201
    assert response.json()["answer_mode"] == "assistive"


async def test_create_workspace_assigns_owner_membership(client, session_factory):
    headers = await auth_headers(client, "owner@example.com")
    me = await client.get("/api/v1/auth/me", headers=headers)
    workspace = await create_workspace(client, headers)

    async with session_factory() as session:
        membership = (
            await session.exec(
                select(Membership).where(Membership.workspace_id == workspace.json()["id"])
            )
        ).one()

    assert membership.user_id == me.json()["id"]
    assert membership.role is MembershipRole.OWNER


async def test_create_workspace_rejects_duplicate_slug(client):
    headers = await auth_headers(client, "owner@example.com")
    await create_workspace(client, headers)

    response = await create_workspace(client, headers)

    assert response.status_code == 409
    assert response.json()["code"] == "SLUG_ALREADY_TAKEN"


async def test_create_workspace_requires_authentication(client):
    response = await client.post(WORKSPACES_URL, json={"name": "Acme", "slug": "acme"})

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_create_workspace_rejects_blank_name(client):
    headers = await auth_headers(client, "owner@example.com")

    response = await create_workspace(client, headers, name="   ")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_list_workspaces_returns_only_memberships(client):
    owner_headers = await auth_headers(client, "owner@example.com")
    other_headers = await auth_headers(client, "other@example.com")

    await create_workspace(client, owner_headers, name="Acme", slug="acme")
    await create_workspace(client, owner_headers, name="Beta", slug="beta")
    await create_workspace(client, other_headers, name="Gamma", slug="gamma")

    owner_list = await client.get(WORKSPACES_URL, headers=owner_headers)
    other_list = await client.get(WORKSPACES_URL, headers=other_headers)

    assert [workspace["slug"] for workspace in owner_list.json()] == ["acme", "beta"]
    assert [workspace["slug"] for workspace in other_list.json()] == ["gamma"]


async def test_list_workspaces_requires_authentication(client):
    response = await client.get(WORKSPACES_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_get_workspace_as_member(client):
    headers = await auth_headers(client, "owner@example.com")
    workspace = await create_workspace(client, headers)

    response = await client.get(f"{WORKSPACES_URL}/{workspace.json()['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["slug"] == "acme"


async def test_get_workspace_as_non_member_returns_403(client):
    owner_headers = await auth_headers(client, "owner@example.com")
    other_headers = await auth_headers(client, "other@example.com")
    workspace = await create_workspace(client, owner_headers)

    response = await client.get(
        f"{WORKSPACES_URL}/{workspace.json()['id']}", headers=other_headers
    )

    assert response.status_code == 403
    assert response.json()["code"] == "NOT_A_MEMBER"


async def test_get_workspace_not_found_returns_404(client):
    headers = await auth_headers(client, "owner@example.com")

    response = await client.get(f"{WORKSPACES_URL}/999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["code"] == "WORKSPACE_NOT_FOUND"


async def test_get_workspace_requires_authentication(client):
    owner_headers = await auth_headers(client, "owner@example.com")
    workspace = await create_workspace(client, owner_headers)
    client.cookies.clear()

    response = await client.get(f"{WORKSPACES_URL}/{workspace.json()['id']}")

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def add_membership(session_factory, workspace_id, user_id, role):
    async with session_factory() as session:
        session.add(
            Membership(user_id=user_id, workspace_id=workspace_id, role=role)
        )
        await session.commit()


async def test_update_workspace_as_owner(client):
    headers = await auth_headers(client, "owner@example.com")
    workspace = await create_workspace(client, headers)

    response = await client.patch(
        f"{WORKSPACES_URL}/{workspace.json()['id']}",
        json={
            "name": "Renamed",
            "slug": "renamed",
            "default_locale": "en",
            "answer_mode": "assistive",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["slug"] == "renamed"
    assert body["default_locale"] == "en"
    assert body["answer_mode"] == "assistive"


async def test_update_workspace_keeps_unsent_fields(client):
    headers = await auth_headers(client, "owner@example.com")
    workspace = await create_workspace(client, headers)

    response = await client.patch(
        f"{WORKSPACES_URL}/{workspace.json()['id']}",
        json={"name": "Only name"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Only name"
    assert response.json()["slug"] == "acme"
    assert response.json()["default_locale"] == "it"


async def test_update_workspace_allows_keeping_own_slug(client):
    headers = await auth_headers(client, "owner@example.com")
    workspace = await create_workspace(client, headers)

    response = await client.patch(
        f"{WORKSPACES_URL}/{workspace.json()['id']}",
        json={"slug": "acme"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["slug"] == "acme"


async def test_update_workspace_rejects_duplicate_slug(client):
    headers = await auth_headers(client, "owner@example.com")
    await create_workspace(client, headers, name="Acme", slug="acme")
    other = await create_workspace(client, headers, name="Beta", slug="beta")

    response = await client.patch(
        f"{WORKSPACES_URL}/{other.json()['id']}",
        json={"slug": "acme"},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "SLUG_ALREADY_TAKEN"


async def test_update_workspace_normalizes_slug(client):
    headers = await auth_headers(client, "owner@example.com")
    workspace = await create_workspace(client, headers)

    response = await client.patch(
        f"{WORKSPACES_URL}/{workspace.json()['id']}",
        json={"slug": "My New Slug!!"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["slug"] == "my-new-slug"


async def test_update_workspace_rejects_invalid_slug(client):
    headers = await auth_headers(client, "owner@example.com")
    workspace = await create_workspace(client, headers)

    response = await client.patch(
        f"{WORKSPACES_URL}/{workspace.json()['id']}",
        json={"slug": "!!!"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_update_workspace_rejects_blank_name(client):
    headers = await auth_headers(client, "owner@example.com")
    workspace = await create_workspace(client, headers)

    response = await client.patch(
        f"{WORKSPACES_URL}/{workspace.json()['id']}",
        json={"name": "   "},
        headers=headers,
    )

    assert response.status_code == 422


async def test_update_workspace_as_admin(client, session_factory):
    owner_headers = await auth_headers(client, "owner@example.com")
    admin_headers = await auth_headers(client, "admin@example.com")
    workspace = await create_workspace(client, owner_headers)
    admin_id = await user_id_for(client, admin_headers)
    await add_membership(
        session_factory, workspace.json()["id"], admin_id, MembershipRole.ADMIN
    )

    response = await client.patch(
        f"{WORKSPACES_URL}/{workspace.json()['id']}",
        json={"name": "By admin"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "By admin"


async def test_update_workspace_as_member_is_forbidden(client, session_factory):
    owner_headers = await auth_headers(client, "owner@example.com")
    member_headers = await auth_headers(client, "member@example.com")
    workspace = await create_workspace(client, owner_headers)
    member_id = await user_id_for(client, member_headers)
    await add_membership(
        session_factory, workspace.json()["id"], member_id, MembershipRole.MEMBER
    )

    response = await client.patch(
        f"{WORKSPACES_URL}/{workspace.json()['id']}",
        json={"name": "Nope"},
        headers=member_headers,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


async def test_update_workspace_as_non_member_is_forbidden(client):
    owner_headers = await auth_headers(client, "owner@example.com")
    other_headers = await auth_headers(client, "other@example.com")
    workspace = await create_workspace(client, owner_headers)

    response = await client.patch(
        f"{WORKSPACES_URL}/{workspace.json()['id']}",
        json={"name": "Nope"},
        headers=other_headers,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "NOT_A_MEMBER"


async def test_update_workspace_requires_authentication(client):
    owner_headers = await auth_headers(client, "owner@example.com")
    workspace = await create_workspace(client, owner_headers)
    client.cookies.clear()

    response = await client.patch(
        f"{WORKSPACES_URL}/{workspace.json()['id']}", json={"name": "Nope"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_update_workspace_not_found(client):
    headers = await auth_headers(client, "owner@example.com")

    response = await client.patch(
        f"{WORKSPACES_URL}/999999", json={"name": "Nope"}, headers=headers
    )

    assert response.status_code == 404
    assert response.json()["code"] == "WORKSPACE_NOT_FOUND"


async def test_update_workspace_can_deactivate(client):
    headers = await auth_headers(client, "owner@example.com")
    workspace = await create_workspace(client, headers)

    response = await client.patch(
        f"{WORKSPACES_URL}/{workspace.json()['id']}",
        json={"is_active": False},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_delete_workspace_as_owner(client):
    headers = await auth_headers(client, "owner@example.com")
    workspace = await create_workspace(client, headers)

    response = await client.delete(
        f"{WORKSPACES_URL}/{workspace.json()['id']}", headers=headers
    )

    assert response.status_code == 204
    after = await client.get(f"{WORKSPACES_URL}/{workspace.json()['id']}", headers=headers)
    assert after.status_code == 404
    assert after.json()["code"] == "WORKSPACE_NOT_FOUND"


async def test_delete_workspace_cascades_memberships(client, session_factory):
    headers = await auth_headers(client, "owner@example.com")
    workspace = await create_workspace(client, headers)
    workspace_id = workspace.json()["id"]

    await client.delete(f"{WORKSPACES_URL}/{workspace_id}", headers=headers)

    async with session_factory() as session:
        remaining = (
            await session.exec(
                select(Membership).where(Membership.workspace_id == workspace_id)
            )
        ).all()
    assert remaining == []


async def test_delete_workspace_as_admin_is_forbidden(client, session_factory):
    owner_headers = await auth_headers(client, "owner@example.com")
    admin_headers = await auth_headers(client, "admin@example.com")
    workspace = await create_workspace(client, owner_headers)
    admin_id = await user_id_for(client, admin_headers)
    await add_membership(
        session_factory, workspace.json()["id"], admin_id, MembershipRole.ADMIN
    )

    response = await client.delete(
        f"{WORKSPACES_URL}/{workspace.json()['id']}", headers=admin_headers
    )

    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


async def test_delete_workspace_as_member_is_forbidden(client, session_factory):
    owner_headers = await auth_headers(client, "owner@example.com")
    member_headers = await auth_headers(client, "member@example.com")
    workspace = await create_workspace(client, owner_headers)
    member_id = await user_id_for(client, member_headers)
    await add_membership(
        session_factory, workspace.json()["id"], member_id, MembershipRole.MEMBER
    )

    response = await client.delete(
        f"{WORKSPACES_URL}/{workspace.json()['id']}", headers=member_headers
    )

    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


async def test_delete_workspace_as_non_member_is_forbidden(client):
    owner_headers = await auth_headers(client, "owner@example.com")
    other_headers = await auth_headers(client, "other@example.com")
    workspace = await create_workspace(client, owner_headers)

    response = await client.delete(
        f"{WORKSPACES_URL}/{workspace.json()['id']}", headers=other_headers
    )

    assert response.status_code == 403
    assert response.json()["code"] == "NOT_A_MEMBER"


async def test_delete_workspace_requires_authentication(client):
    headers = await auth_headers(client, "owner@example.com")
    workspace = await create_workspace(client, headers)
    client.cookies.clear()

    response = await client.delete(f"{WORKSPACES_URL}/{workspace.json()['id']}")

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_delete_workspace_not_found(client):
    headers = await auth_headers(client, "owner@example.com")

    response = await client.delete(f"{WORKSPACES_URL}/999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["code"] == "WORKSPACE_NOT_FOUND"
