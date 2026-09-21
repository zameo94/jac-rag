from __future__ import annotations

from app.schemas.tenant import AnswerMode
from app.services.llm.base import LLMProvider
from app.services.rag.chat.prompt import build_messages, refusal_message
from app.services.rag.vector_store import RetrievedChunk


async def generate_reply(
    provider: LLMProvider,
    question: str,
    chunks: list[RetrievedChunk],
    *,
    answer_mode: AnswerMode,
    locale: str | None,
) -> tuple[str, list[RetrievedChunk]]:
    """Generate one reply with the single selected provider.

    In strict mode with no grounded context the refusal is deterministic and the
    provider is not called. ``chunks`` are only the chunks actually used.
    """
    if answer_mode is AnswerMode.STRICT and not chunks:
        return refusal_message(locale), []
    response = await provider.generate(
        build_messages(question, chunks, answer_mode=answer_mode, locale=locale)
    )
    return response.content, list(chunks)
