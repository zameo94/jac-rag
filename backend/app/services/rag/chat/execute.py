from __future__ import annotations

import asyncio
import logging
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

logger = logging.getLogger(__name__)

PARTIAL_ERROR_CODE = "CLIENT_DISCONNECTED"
INTERNAL_ERROR_CODE = "STREAM_INTERNAL_ERROR"


def _sources_payload(prepared: PreparedChat, sources: list[dict]) -> dict:
    return {
        "conversation_id": prepared.conversation.id,
        "grounded": prepared.grounded,
        "sources": sources,
    }


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
    yield sse_event("sources", _sources_payload(prepared, sources))

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
        partial = "".join(pieces)
        async with session_scope() as session:
            await append_message(
                session,
                prepared.conversation.id,
                role=MessageRole.ASSISTANT,
                content=partial or exc.message,
                provider=prepared.provider_id,
                model=prepared.model,
                grounded=False,
                error_code=exc.code,
            )
        yield sse_event("error", {"code": exc.code, "message": exc.message})
        return
    except Exception:
        logger.exception(
            "chat stream failed with an unexpected error (conversation %s)",
            prepared.conversation.id,
        )
        partial = "".join(pieces)
        async with session_scope() as session:
            await append_message(
                session,
                prepared.conversation.id,
                role=MessageRole.ASSISTANT,
                content=partial or "Unexpected error",
                provider=prepared.provider_id,
                model=prepared.model,
                grounded=False,
                error_code=INTERNAL_ERROR_CODE,
            )
        yield sse_event(
            "error",
            {
                "code": INTERNAL_ERROR_CODE,
                "message": "The stream failed with an unexpected error",
            },
        )
        return
    except (GeneratorExit, asyncio.CancelledError):
        partial = "".join(pieces)
        if partial:
            await _persist_in_background(
                prepared, content=partial, sources=sources
            )
        raise
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


async def _persist_in_background(
    prepared: PreparedChat, *, content: str, sources: list[dict]
) -> None:
    """Best-effort save of a partial reply once the client has disconnected.

    Runs in a shielded task so the write survives the response task being
    cancelled; a failure here must never break the disconnect path.
    """

    async def _save() -> None:
        async with session_scope() as session:
            await append_message(
                session,
                prepared.conversation.id,
                role=MessageRole.ASSISTANT,
                content=content,
                provider=prepared.provider_id,
                model=prepared.model,
                grounded=False,
                error_code=PARTIAL_ERROR_CODE,
                sources=sources,
            )

    future = asyncio.create_task(_save())

    def _consume(_task: asyncio.Task) -> None:
        _task.exception()

    future.add_done_callback(_consume)
    try:
        await asyncio.shield(future)
    except asyncio.CancelledError:
        pass
