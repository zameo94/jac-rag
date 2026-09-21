from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import session_scope
from app.schemas.conversation import MessageRole
from app.services.llm.base import LLMProviderError
from app.services.rag.chat.conversations import add_message, append_message
from app.services.rag.chat.events import sse_event
from app.services.rag.chat.prepare import PreparedChat, chunk_sources
from app.services.rag.chat.reply import generate_reply, stream_reply
from app.services.rag.vector_store import RetrievedChunk


async def execute_reply(
    session: AsyncSession, prepared: PreparedChat, message: str
) -> tuple[str, list[RetrievedChunk]]:
    """Persist both turns for a non-streaming reply and return answer + used chunks."""
    await add_message(
        session, prepared.conversation, role=MessageRole.USER, content=message
    )
    try:
        answer, used = await generate_reply(
            prepared.provider,
            message,
            prepared.used_chunks,
            answer_mode=prepared.answer_mode,
            locale=prepared.locale,
            history=prepared.history,
        )
    except LLMProviderError as exc:
        await add_message(
            session,
            prepared.conversation,
            role=MessageRole.ASSISTANT,
            content=exc.message,
            provider=prepared.provider_id,
            model=prepared.model,
            grounded=False,
            error_code=exc.code,
        )
        raise

    await add_message(
        session,
        prepared.conversation,
        role=MessageRole.ASSISTANT,
        content=answer,
        provider=prepared.provider_id,
        model=prepared.model,
        grounded=prepared.grounded,
        sources=chunk_sources(used),
    )
    return answer, used


async def stream_events(
    prepared: PreparedChat, message: str
) -> AsyncGenerator[str, None]:
    """SSE stream for one reply. The provider is always closed here, never by the route."""
    sources = chunk_sources(prepared.used_chunks)
    yield sse_event("sources", {"grounded": prepared.grounded, "sources": sources})

    pieces: list[str] = []
    try:
        async for piece in stream_reply(
            prepared.provider,
            message,
            prepared.used_chunks,
            answer_mode=prepared.answer_mode,
            locale=prepared.locale,
            history=prepared.history,
        ):
            pieces.append(piece)
            yield sse_event("token", {"text": piece})
    except LLMProviderError as exc:
        async with session_scope() as session:
            await append_message(
                session,
                prepared.conversation.id,
                role=MessageRole.ASSISTANT,
                content=exc.message,
                provider=prepared.provider_id,
                model=prepared.model,
                grounded=False,
                error_code=exc.code,
            )
        yield sse_event("error", {"code": exc.code, "message": exc.message})
        return
    finally:
        await prepared.provider.aclose()

    async with session_scope() as session:
        await append_message(
            session,
            prepared.conversation.id,
            role=MessageRole.ASSISTANT,
            content="".join(pieces),
            provider=prepared.provider_id,
            model=prepared.model,
            grounded=prepared.grounded,
            sources=sources,
        )
    yield sse_event(
        "done",
        {
            "provider": prepared.provider_id,
            "model": prepared.model,
            "grounded": prepared.grounded,
        },
    )
