from datetime import timedelta

from sqlmodel import select

from app.core.datetimes import utcnow
from app.models import Conversation, Membership, Message
from app.schemas.conversation import MessageRole
from app.schemas.membership import MembershipRole
from tests.helpers import register_and_login, user_id_for


async def create_workspace(client, headers, name: str = "Acme") -> int:
    response = await client.post("/api/v1/workspaces", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def seed_conversation(
    session_factory, workspace_id: int, user_id: int, *, title: str, minutes_ago: int = 0
) -> int:
    async with session_factory() as session:
        conversation = Conversation(
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            updated_at=utcnow() - timedelta(minutes=minutes_ago),
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        session.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="ciao",
            )
        )
        await session.commit()
        return conversation.id


async def add_member(session_factory, user_id: int, workspace_id: int) -> None:
    async with session_factory() as session:
        session.add(
            Membership(
                user_id=user_id, workspace_id=workspace_id, role=MembershipRole.MEMBER
            )
        )
        await session.commit()


async def test_list_and_get_conversation_for_owner(client, session_factory):
    headers = await register_and_login(client, "conv-owner@example.com")
    owner_id = await user_id_for(client, headers)
    workspace_id = await create_workspace(client, headers)
    older = await seed_conversation(
        session_factory, workspace_id, owner_id, title="Older", minutes_ago=10
    )
    newer = await seed_conversation(
        session_factory, workspace_id, owner_id, title="Newer", minutes_ago=1
    )

    listed = await client.get(
        f"/api/v1/workspaces/{workspace_id}/conversations", headers=headers
    )
    detail = await client.get(
        f"/api/v1/workspaces/{workspace_id}/conversations/{newer}", headers=headers
    )

    assert listed.status_code == 200
    assert [c["id"] for c in listed.json()] == [newer, older]
    assert "messages" not in listed.json()[0]
    assert detail.status_code == 200
    assert [m["role"] for m in detail.json()["messages"]] == ["user"]


async def test_conversation_list_pagination(client, session_factory):
    headers = await register_and_login(client, "conv-page@example.com")
    owner_id = await user_id_for(client, headers)
    workspace_id = await create_workspace(client, headers)
    for index in range(3):
        await seed_conversation(
            session_factory, workspace_id, owner_id, title=f"C{index}", minutes_ago=index
        )

    first_page = await client.get(
        f"/api/v1/workspaces/{workspace_id}/conversations?limit=2", headers=headers
    )
    second_page = await client.get(
        f"/api/v1/workspaces/{workspace_id}/conversations?limit=2&offset=2", headers=headers
    )

    assert len(first_page.json()) == 2
    assert len(second_page.json()) == 1


async def test_conversations_require_manager_role(client, session_factory):
    owner_headers = await register_and_login(client, "conv-manager@example.com")
    workspace_id = await create_workspace(client, owner_headers)

    member_headers = await register_and_login(client, "conv-member@example.com")
    member_id = await user_id_for(client, member_headers)
    await add_member(session_factory, member_id, workspace_id)

    listed = await client.get(
        f"/api/v1/workspaces/{workspace_id}/conversations", headers=member_headers
    )

    assert listed.status_code == 403
    assert listed.json()["code"] == "INSUFFICIENT_ROLE"


async def test_conversations_reject_non_member_and_anonymous(client):
    owner_headers = await register_and_login(client, "conv-a@example.com")
    workspace_id = await create_workspace(client, owner_headers)
    other_headers = await register_and_login(client, "conv-b@example.com")

    other = await client.get(
        f"/api/v1/workspaces/{workspace_id}/conversations", headers=other_headers
    )
    client.cookies.clear()
    anonymous = await client.get(f"/api/v1/workspaces/{workspace_id}/conversations")

    assert other.status_code == 403
    assert other.json()["code"] == "NOT_A_MEMBER"
    assert anonymous.status_code == 401


async def test_conversation_scoped_to_workspace(client, session_factory):
    first_headers = await register_and_login(client, "conv-first@example.com")
    first_id = await user_id_for(client, first_headers)
    first_workspace = await create_workspace(client, first_headers, name="First Co")
    conversation_id = await seed_conversation(
        session_factory, first_workspace, first_id, title="Secret"
    )

    second_headers = await register_and_login(client, "conv-second@example.com")
    second_workspace = await create_workspace(client, second_headers, name="Second Co")

    detail = await client.get(
        f"/api/v1/workspaces/{second_workspace}/conversations/{conversation_id}",
        headers=second_headers,
    )
    deleted = await client.delete(
        f"/api/v1/workspaces/{second_workspace}/conversations/{conversation_id}",
        headers=second_headers,
    )

    assert detail.status_code == 404
    assert deleted.status_code == 404


async def test_delete_conversation(client, session_factory):
    headers = await register_and_login(client, "conv-delete@example.com")
    owner_id = await user_id_for(client, headers)
    workspace_id = await create_workspace(client, headers)
    conversation_id = await seed_conversation(
        session_factory, workspace_id, owner_id, title="To delete"
    )

    response = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/conversations/{conversation_id}", headers=headers
    )

    assert response.status_code == 204
    detail = await client.get(
        f"/api/v1/workspaces/{workspace_id}/conversations/{conversation_id}", headers=headers
    )
    assert detail.status_code == 404
    async with session_factory() as session:
        assert await session.get(Conversation, conversation_id) is None
