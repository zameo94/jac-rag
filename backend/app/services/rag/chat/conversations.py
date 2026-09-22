from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.datetimes import utcnow
from app.core.errors import api_error
from app.models import Conversation, Message
from app.schemas.conversation import MessageRole
from app.services.llm.base import LLMMessage, LLMRole

TITLE_MAX_LENGTH = 80

_ROLE_TO_LLM = {
    MessageRole.USER: LLMRole.USER,
    MessageRole.ASSISTANT: LLMRole.ASSISTANT,
}


def make_title(question: str) -> str:
    return " ".join(question.split())[:TITLE_MAX_LENGTH]


def _same_actor(
    conversation: Conversation, user_id: int | None, end_user_id: str | None
) -> bool:
    return conversation.user_id == user_id and conversation.end_user_id == end_user_id


async def resolve_conversation(
    session: AsyncSession,
    tenant_id: int,
    *,
    user_id: int | None,
    end_user_id: str | None,
    conversation_id: int | None,
    title_source: str,
) -> Conversation:
    if conversation_id is not None:
        conversation = await session.get(Conversation, conversation_id)
        if (
            conversation is None
            or conversation.tenant_id != tenant_id
            or not _same_actor(conversation, user_id, end_user_id)
        ):
            raise api_error(404, "CONVERSATION_NOT_FOUND", "Conversation not found")
        return conversation

    conversation = Conversation(
        tenant_id=tenant_id,
        user_id=user_id,
        end_user_id=end_user_id,
        title=make_title(title_source),
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def load_history(
    session: AsyncSession, conversation_id: int, limit: int
) -> list[Message]:
    """Load the last ``limit`` messages, skipping failed/garbage assistant turns."""
    if limit <= 0:
        return []
    statement = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.error_code.is_(None),
        )
        .order_by(Message.id.desc())
        .limit(limit)
    )
    messages = list((await session.exec(statement)).all())
    messages.reverse()
    return messages


async def add_message(
    session: AsyncSession,
    conversation: Conversation,
    *,
    role: MessageRole,
    content: str,
    provider: str | None = None,
    model: str | None = None,
    grounded: bool | None = None,
    error_code: str | None = None,
    sources: list[dict] | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
        provider=provider,
        model=model,
        grounded=grounded,
        error_code=error_code,
        sources=sources,
    )
    conversation.updated_at = utcnow()
    session.add(message)
    session.add(conversation)
    await session.commit()
    await session.refresh(message)
    return message


async def append_message(
    session: AsyncSession,
    conversation_id: int,
    *,
    role: MessageRole,
    content: str,
    provider: str | None = None,
    model: str | None = None,
    grounded: bool | None = None,
    error_code: str | None = None,
    sources: list[dict] | None = None,
) -> Message | None:
    """Persist a message by conversation id (used after a stream closes its session)."""
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        return None
    return await add_message(
        session,
        conversation,
        role=role,
        content=content,
        provider=provider,
        model=model,
        grounded=grounded,
        error_code=error_code,
        sources=sources,
    )


def to_llm_messages(messages: list[Message]) -> list[LLMMessage]:
    return [
        LLMMessage(role=_ROLE_TO_LLM[message.role], content=message.content)
        for message in messages
    ]
