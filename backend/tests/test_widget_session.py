import pytest
from fastapi import HTTPException

from app.core import security
from app.core.deps import get_widget_visitor, resolve_widget_visitor
from app.models import ApiKey, Workspace
from tests.helpers import register_and_login, user_id_for


async def create_workspace(client, headers, name: str = "Acme") -> int:
    response = await client.post("/api/v1/workspaces", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def add_key(
    session_factory, workspace_id: int, user_id: int, *, active: bool = True
) -> str:
    plaintext = security.generate_embed_key()
    async with session_factory() as session:
        session.add(
            ApiKey(
                workspace_id=workspace_id,
                name="Widget",
                prefix=security.embed_key_prefix(plaintext),
                key_hash=security.hash_token(plaintext),
                created_by=user_id,
                is_active=active,
            )
        )
        await session.commit()
    return plaintext


async def add_workspace(session_factory, name: str = "Direct Co") -> Workspace:
    async with session_factory() as session:
        workspace = Workspace(name=name, slug=name.lower().replace(" ", "-"))
        session.add(workspace)
        await session.commit()
        await session.refresh(workspace)
        return workspace


async def test_create_widget_session(client, session_factory):
    headers = await register_and_login(client, "widget-owner@example.com")
    owner_id = await user_id_for(client, headers)
    workspace_id = await create_workspace(client, headers)
    plaintext = await add_key(session_factory, workspace_id, owner_id)

    response = await client.post(
        "/api/v1/widget/session", headers={"X-Embed-Key": plaintext}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workspace_id"] == workspace_id
    assert body["expires_in"] == 30 * 86400
    identity = security.decode_visitor_token(body["visitor_token"])
    assert identity.workspace_id == workspace_id
    assert identity.subject


async def test_widget_session_requires_valid_key(client):
    missing = await client.post("/api/v1/widget/session")
    invalid = await client.post(
        "/api/v1/widget/session", headers={"X-Embed-Key": "jrk_nope"}
    )

    assert missing.status_code == 401
    assert missing.json()["code"] == "EMBED_KEY_REQUIRED"
    assert invalid.status_code == 401
    assert invalid.json()["code"] == "INVALID_EMBED_KEY"


async def test_widget_session_rejects_disabled_key(client, session_factory):
    headers = await register_and_login(client, "widget-disabled@example.com")
    owner_id = await user_id_for(client, headers)
    workspace_id = await create_workspace(client, headers)
    plaintext = await add_key(session_factory, workspace_id, owner_id, active=False)

    response = await client.post(
        "/api/v1/widget/session", headers={"X-Embed-Key": plaintext}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "EMBED_KEY_DISABLED"


async def test_sessions_have_distinct_subjects(client, session_factory):
    headers = await register_and_login(client, "widget-unique@example.com")
    owner_id = await user_id_for(client, headers)
    workspace_id = await create_workspace(client, headers)
    plaintext = await add_key(session_factory, workspace_id, owner_id)

    first = await client.post(
        "/api/v1/widget/session", headers={"X-Embed-Key": plaintext}
    )
    second = await client.post(
        "/api/v1/widget/session", headers={"X-Embed-Key": plaintext}
    )

    first_subject = security.decode_visitor_token(first.json()["visitor_token"]).subject
    second_subject = security.decode_visitor_token(
        second.json()["visitor_token"]
    ).subject
    assert first_subject != second_subject


async def test_resolve_widget_visitor_valid(session_factory):
    workspace = await add_workspace(session_factory)
    token = security.create_visitor_token(workspace.id)

    identity = await resolve_widget_visitor(workspace, token)

    assert identity.workspace_id == workspace.id
    assert identity.subject


async def test_get_widget_visitor_reads_header(session_factory):
    workspace = await add_workspace(session_factory)
    token = security.create_visitor_token(workspace.id)

    identity = await get_widget_visitor(token, workspace)

    assert identity.workspace_id == workspace.id


async def test_resolve_widget_visitor_missing(session_factory):
    workspace = await add_workspace(session_factory)

    with pytest.raises(HTTPException) as exc:
        await resolve_widget_visitor(workspace, None)

    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "VISITOR_TOKEN_REQUIRED"


async def test_resolve_widget_visitor_invalid(session_factory):
    workspace = await add_workspace(session_factory)

    with pytest.raises(HTTPException) as exc:
        await resolve_widget_visitor(workspace, "not-a-token")

    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "INVALID_VISITOR_TOKEN"


async def test_resolve_widget_visitor_workspace_mismatch(session_factory):
    workspace = await add_workspace(session_factory)
    token = security.create_visitor_token(workspace.id + 999)

    with pytest.raises(HTTPException) as exc:
        await resolve_widget_visitor(workspace, token)

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "VISITOR_WORKSPACE_MISMATCH"
