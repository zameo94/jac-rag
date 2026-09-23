from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from qdrant_client import AsyncQdrantClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.deps import (
    authenticate_user,
    bearer_scheme,
    ensure_workspace_active,
    get_current_membership,
    get_current_user,
    load_membership,
)
from app.core.errors import api_error
from app.database import get_session, session_scope
from app.models import Membership, Workspace, User
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource
from app.schemas.conversation import MessageRole
from app.services.llm.base import LLMProviderError
from app.services.rag import vector_store
from app.services.rag.chat.conversations import add_message
from app.services.rag.chat.execute import execute_reply, stream_events
from app.services.rag.chat.prepare import chunk_sources, prepare_chat

router = APIRouter()

PROVIDER_ERROR_STATUS = {
    "PROVIDER_NOT_AVAILABLE": status.HTTP_403_FORBIDDEN,
    "PROVIDER_NOT_SELECTED": status.HTTP_409_CONFLICT,
    "NO_PROVIDER_AVAILABLE": status.HTTP_409_CONFLICT,
    "PROVIDER_NOT_CONFIGURED": status.HTTP_409_CONFLICT,
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


@router.post("/{workspace_id}/chat", response_model=ChatResponse)
async def chat(
    workspace_id: int,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
    client: AsyncQdrantClient = Depends(get_vector_client),
) -> ChatResponse:
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "WORKSPACE_NOT_FOUND", "Workspace not found")
    ensure_workspace_active(workspace)

    try:
        prepared = await prepare_chat(
            session,
            client,
            workspace=workspace,
            message=payload.message,
            conversation_id=payload.conversation_id,
            user=current_user,
        )
    except LLMProviderError as exc:
        raise provider_error(exc)

    try:
        answer_text, used_chunks = await execute_reply(
            session, prepared, payload.message
        )
    except LLMProviderError as exc:
        raise provider_error(exc)
    finally:
        await prepared.provider.aclose()

    return ChatResponse(
        conversation_id=prepared.conversation.id,
        answer=answer_text,
        provider=prepared.provider_id,
        model=prepared.model,
        grounded=prepared.grounded,
        sources=[ChatSource(**source) for source in chunk_sources(used_chunks)],
    )


@router.post("/{workspace_id}/chat/stream")
async def chat_stream(
    workspace_id: int,
    payload: ChatRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    client: AsyncQdrantClient = Depends(get_vector_client),
) -> StreamingResponse:
    async with session_scope() as session:
        user = await authenticate_user(session, request, credentials)
        await load_membership(session, user, workspace_id)
        workspace = await session.get(Workspace, workspace_id)
        ensure_workspace_active(workspace)
        try:
            prepared = await prepare_chat(
                session,
                client,
                workspace=workspace,
                message=payload.message,
                conversation_id=payload.conversation_id,
                user=user,
            )
            await add_message(
                session,
                prepared.conversation,
                role=MessageRole.USER,
                content=payload.message,
            )
        except LLMProviderError as exc:
            raise provider_error(exc)

    return StreamingResponse(
        stream_events(prepared, payload.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
