from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, status
from qdrant_client import AsyncQdrantClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.deps import get_current_membership, get_current_user
from app.core.errors import api_error
from app.database import get_session
from app.models import Membership, Tenant, User
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource
from app.services.llm.base import LLMProviderError
from app.services.llm.factory import create_provider, resolve_model
from app.services.llm.tenant import tenant_model_override
from app.services.llm.user import resolve_user_provider
from app.services.rag import vector_store
from app.services.rag.chat import generate_reply
from app.services.rag.retrieve import has_context, retrieve_chunks

router = APIRouter()

PROVIDER_ERROR_STATUS = {
    "PROVIDER_NOT_AVAILABLE": status.HTTP_403_FORBIDDEN,
    "PROVIDER_NOT_SELECTED": status.HTTP_409_CONFLICT,
    "NO_PROVIDER_AVAILABLE": status.HTTP_409_CONFLICT,
    "PROVIDER_NOT_IMPLEMENTED": status.HTTP_501_NOT_IMPLEMENTED,
    "LLM_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    "LLM_HTTP_ERROR": status.HTTP_502_BAD_GATEWAY,
    "LLM_GENERATION_ERROR": status.HTTP_502_BAD_GATEWAY,
    "LLM_INVALID_RESPONSE": status.HTTP_502_BAD_GATEWAY,
}


def provider_error(exc: LLMProviderError):
    status_code = PROVIDER_ERROR_STATUS.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    return api_error(status_code, exc.code, exc.message)


async def get_vector_client() -> AsyncGenerator[AsyncQdrantClient, None]:
    client = vector_store.get_qdrant_client()
    try:
        yield client
    finally:
        await client.close()


@router.post("/{tenant_id}/chat", response_model=ChatResponse)
async def chat(
    tenant_id: int,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
    client: AsyncQdrantClient = Depends(get_vector_client),
) -> ChatResponse:
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "TENANT_NOT_FOUND", "Tenant not found")

    try:
        capability = await resolve_user_provider(session, tenant_id, current_user.id)
        model_override = await tenant_model_override(session, tenant_id)
        model = resolve_model(capability.id, model_override)
        provider = create_provider(capability.id, model=model_override)
    except LLMProviderError as exc:
        raise provider_error(exc)

    try:
        chunks = await retrieve_chunks(client, tenant_id, payload.message)
        grounded = has_context(chunks)
        used = chunks if grounded else []
        answer_text, used_chunks = await generate_reply(
            provider,
            payload.message,
            used,
            answer_mode=tenant.answer_mode,
            locale=current_user.locale or tenant.default_locale,
        )
    except LLMProviderError as exc:
        raise provider_error(exc)
    finally:
        await provider.aclose()

    return ChatResponse(
        answer=answer_text,
        provider=capability.id,
        model=model,
        grounded=grounded,
        sources=[
            ChatSource(
                document_id=chunk.document_id,
                filename=chunk.filename,
                chunk_index=chunk.chunk_index,
                score=chunk.score,
            )
            for chunk in used_chunks
        ],
    )
