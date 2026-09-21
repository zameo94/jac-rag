from datetime import timedelta

from sqlmodel import select

from app.core.datetimes import utcnow
from app.models import Conversation, Message
from app.schemas.conversation import MessageRole
from app.tasks.retention import purge_conversations, purge_old_conversations


async def seed(session_factory, *, days_ago: int) -> int:
    async with session_factory() as session:
        conversation = Conversation(
            tenant_id=1,
            user_id=1,
            title="t",
            updated_at=utcnow() - timedelta(days=days_ago),
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


async def test_purge_removes_old_and_keeps_recent(session_factory):
    await seed(session_factory, days_ago=40)
    recent_id = await seed(session_factory, days_ago=1)

    removed = await purge_old_conversations(session_factory, retention_days=30)

    assert removed == 1
    async with session_factory() as session:
        conversations = (await session.exec(select(Conversation))).all()
        messages = (await session.exec(select(Message))).all()
    assert [conversation.id for conversation in conversations] == [recent_id]
    assert len(messages) == 1


async def test_purge_disabled_when_zero(session_factory):
    await seed(session_factory, days_ago=400)

    removed = await purge_old_conversations(session_factory, retention_days=0)

    assert removed == 0
    async with session_factory() as session:
        assert len((await session.exec(select(Conversation))).all()) == 1


def test_purge_task_is_scheduled():
    assert "schedule" in purge_conversations.labels
