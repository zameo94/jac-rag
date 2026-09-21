import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, select

from app.database import create_engine, create_session_factory
from app.models import Conversation, Message, Tenant, User
from app.schemas.conversation import MessageRole


@pytest.fixture
async def fk_session_factory():
    engine = create_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)

    yield create_session_factory(engine)
    await engine.dispose()


async def seed(session_factory) -> tuple[int, int]:
    async with session_factory() as session:
        tenant = Tenant(name="Acme", slug="acme")
        user = User(email="owner@example.com", locale="it", password_hash="hash")
        session.add(tenant)
        session.add(user)
        await session.commit()
        await session.refresh(tenant)
        await session.refresh(user)
        return tenant.id, user.id


async def test_conversation_for_user_persists(fk_session_factory):
    tenant_id, user_id = await seed(fk_session_factory)

    async with fk_session_factory() as session:
        conversation = Conversation(tenant_id=tenant_id, user_id=user_id, title="Hello")
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)

    assert conversation.id is not None
    assert conversation.user_id == user_id
    assert conversation.end_user_id is None
    assert conversation.created_at is not None


async def test_conversation_for_end_user_persists(fk_session_factory):
    tenant_id, _ = await seed(fk_session_factory)

    async with fk_session_factory() as session:
        conversation = Conversation(tenant_id=tenant_id, end_user_id="visitor-1")
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)

    assert conversation.end_user_id == "visitor-1"
    assert conversation.user_id is None
    assert conversation.title is None


async def test_conversation_without_actor_is_rejected(fk_session_factory):
    tenant_id, _ = await seed(fk_session_factory)

    async with fk_session_factory() as session:
        session.add(Conversation(tenant_id=tenant_id))
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_conversation_with_two_actors_is_rejected(fk_session_factory):
    tenant_id, user_id = await seed(fk_session_factory)

    async with fk_session_factory() as session:
        session.add(
            Conversation(
                tenant_id=tenant_id, user_id=user_id, end_user_id="visitor-1"
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_messages_load_with_conversation(fk_session_factory):
    tenant_id, _ = await seed(fk_session_factory)

    async with fk_session_factory() as session:
        conversation = Conversation(tenant_id=tenant_id, end_user_id="visitor-1")
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        session.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="Ciao",
            )
        )
        session.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content="Risposta",
                provider="ollama",
                model="llama3.2",
                grounded=True,
                sources=[{"document_id": 1, "filename": "doc.md"}],
            )
        )
        await session.commit()
        conversation_id = conversation.id

    async with fk_session_factory() as session:
        loaded = (
            await session.exec(
                select(Conversation)
                .where(Conversation.id == conversation_id)
                .options(selectinload(Conversation.messages))
            )
        ).one()

    assert [message.role for message in loaded.messages] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]
    assert loaded.messages[1].sources == [{"document_id": 1, "filename": "doc.md"}]


async def test_deleting_conversation_cascades_messages(fk_session_factory):
    tenant_id, _ = await seed(fk_session_factory)

    async with fk_session_factory() as session:
        conversation = Conversation(tenant_id=tenant_id, end_user_id="visitor-1")
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        session.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="Ciao",
            )
        )
        await session.commit()
        conversation_id = conversation.id

    async with fk_session_factory() as session:
        loaded = await session.get(Conversation, conversation_id)
        await session.delete(loaded)
        await session.commit()

    async with fk_session_factory() as session:
        remaining = (await session.exec(select(Message))).all()

    assert remaining == []
