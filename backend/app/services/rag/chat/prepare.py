from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.models import Conversation, Tenant, User
from app.schemas.tenant import AnswerMode
from app.services.llm.base import LLMMessage, LLMProvider
from app.services.llm.factory import build_provider
from app.services.llm.resolution.tenant import tenant_model_override
from app.services.llm.resolution.user import (
    resolve_tenant_provider,
    resolve_user_provider,
)
from app.services.rag.chat.conversations import (
    load_history,
    resolve_conversation,
    to_llm_messages,
)
from app.services.rag.rerank import release_reranker, rerank_chunks
from app.services.rag.retrieve import has_context, retrieve_chunks
from app.services.rag.vector_store import RetrievedChunk


def chunk_sources(chunks: list[RetrievedChunk]) -> list[dict]:
    return [
        {
            "document_id": chunk.document_id,
            "filename": chunk.filename,
            "chunk_index": chunk.chunk_index,
            "score": chunk.score,
        }
        for chunk in chunks
    ]


@dataclass
class PreparedChat:
    provider: LLMProvider
    provider_id: str
    model: str
    grounded: bool
    used_chunks: list[RetrievedChunk]
    conversation: Conversation
    history: list[LLMMessage]
    answer_mode: AnswerMode
    locale: str | None


async def prepare_chat(
    session: AsyncSession,
    client: AsyncQdrantClient,
    *,
    tenant: Tenant,
    message: str,
    conversation_id: int | None = None,
    user: User | None = None,
    end_user_id: str | None = None,
) -> PreparedChat:
    """Resolve provider, context and conversation shared by JSON and SSE routes.

    A CMS request passes ``user``; the widget passes ``end_user_id`` instead.
    Retrieval/rerank run before the response starts so no DB/Qdrant resource is
    needed while streaming.
    """
    if user is not None:
        capability = await resolve_user_provider(session, tenant.id, user.id)
        actor_user_id: int | None = user.id
        locale = user.locale or tenant.default_locale
    else:
        capability = await resolve_tenant_provider(session, tenant.id)
        actor_user_id = None
        locale = tenant.default_locale

    model_override = await tenant_model_override(session, tenant.id)
    provider, model = await build_provider(
        session, tenant.id, capability.id, model_override
    )

    try:
        settings = get_settings()
        window = (
            settings.rerank_candidates
            if settings.rerank_enabled
            else settings.retrieval_top_k
        )
        chunks = await retrieve_chunks(client, tenant.id, message, top_k=window)
        grounded = has_context(chunks)
        if not grounded:
            used: list[RetrievedChunk] = []
        elif settings.rerank_enabled:
            used = await rerank_chunks(message, chunks, top_k=settings.chat_context_k)
        else:
            used = chunks[: settings.chat_context_k]
        if settings.rerank_enabled and settings.rerank_mode == "on_demand":
            release_reranker()

        conversation = await resolve_conversation(
            session,
            tenant.id,
            user_id=actor_user_id,
            end_user_id=end_user_id,
            conversation_id=conversation_id,
            title_source=message,
        )
        history = await load_history(
            session, conversation.id, settings.chat_history_limit
        )
    except Exception:
        await provider.aclose()
        raise

    return PreparedChat(
        provider=provider,
        provider_id=capability.id,
        model=model,
        grounded=grounded,
        used_chunks=used,
        conversation=conversation,
        history=to_llm_messages(history),
        answer_mode=tenant.answer_mode,
        locale=locale,
    )
