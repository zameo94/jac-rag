from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import StreamingResponse
from qdrant_client import AsyncQdrantClient
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.chat import get_vector_client, provider_error
from app.core import security
from app.core.config import get_settings
from app.core.deps import (
    enforce_widget_rate_limit,
    ensure_workspace_active,
    get_embed_workspace,
    get_widget_visitor,
    resolve_embed_workspace,
    resolve_widget_visitor,
)
from app.core.errors import api_error
from app.database import get_session, session_scope
from app.models import Conversation, Workspace
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource
from app.schemas.conversation import (
    ConversationDetail,
    ConversationRead,
    MessageRole,
)
from app.schemas.widget import WidgetConfigRead, WidgetSessionRead
from app.services.llm.base import LLMProviderError
from app.services.rate_limit import widget_allowed
from app.services.rag.chat.conversations import add_message
from app.services.rag.chat.execute import execute_reply, stream_events
from app.services.rag.chat.prepare import chunk_sources, prepare_chat

router = APIRouter()

SECONDS_PER_DAY = 86400


@router.post("/session", response_model=WidgetSessionRead)
async def create_widget_session(
    workspace: Workspace = Depends(get_embed_workspace),
    _: None = Depends(enforce_widget_rate_limit),
) -> WidgetSessionRead:
    settings = get_settings()
    return WidgetSessionRead(
        visitor_token=security.create_visitor_token(workspace.id),
        expires_in=settings.visitor_token_expire_days * SECONDS_PER_DAY,
        workspace_id=workspace.id,
    )


@router.get("/config", response_model=WidgetConfigRead)
async def widget_config(
    workspace: Workspace = Depends(get_embed_workspace),
    _: None = Depends(enforce_widget_rate_limit),
) -> WidgetConfigRead:
    return WidgetConfigRead(
        workspace_name=workspace.name,
        default_locale=workspace.default_locale,
        answer_mode=workspace.answer_mode,
        is_active=workspace.is_active,
    )


@router.post("/chat", response_model=ChatResponse)
async def widget_chat(
    payload: ChatRequest,
    workspace: Workspace = Depends(get_embed_workspace),
    visitor: security.VisitorIdentity = Depends(get_widget_visitor),
    _: None = Depends(enforce_widget_rate_limit),
    session: AsyncSession = Depends(get_session),
    client: AsyncQdrantClient = Depends(get_vector_client),
) -> ChatResponse:
    ensure_workspace_active(workspace)
    try:
        prepared = await prepare_chat(
            session,
            client,
            workspace=workspace,
            message=payload.message,
            conversation_id=payload.conversation_id,
            end_user_id=visitor.subject,
            locale_override=payload.locale,
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


@router.post("/chat/stream")
async def widget_chat_stream(
    payload: ChatRequest,
    x_embed_key: str | None = Header(default=None, alias="X-Embed-Key"),
    x_visitor_token: str | None = Header(default=None, alias="X-Visitor-Token"),
    client: AsyncQdrantClient = Depends(get_vector_client),
) -> StreamingResponse:
    async with session_scope() as session:
        workspace = await resolve_embed_workspace(session, x_embed_key)
        ensure_workspace_active(workspace)
        if not await widget_allowed(x_embed_key, workspace.id):
            raise api_error(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "RATE_LIMITED",
                "Too many requests",
            )
        visitor = await resolve_widget_visitor(workspace, x_visitor_token)
        try:
            prepared = await prepare_chat(
                session,
                client,
                workspace=workspace,
                message=payload.message,
                conversation_id=payload.conversation_id,
                end_user_id=visitor.subject,
                locale_override=payload.locale,
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


@router.get("/conversations", response_model=list[ConversationRead])
async def list_widget_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    workspace: Workspace = Depends(get_embed_workspace),
    visitor: security.VisitorIdentity = Depends(get_widget_visitor),
    _: None = Depends(enforce_widget_rate_limit),
    session: AsyncSession = Depends(get_session),
) -> list[Conversation]:
    statement = (
        select(Conversation)
        .where(
            Conversation.workspace_id == workspace.id,
            Conversation.end_user_id == visitor.subject,
        )
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list((await session.exec(statement)).all())


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_widget_conversation(
    conversation_id: int,
    workspace: Workspace = Depends(get_embed_workspace),
    visitor: security.VisitorIdentity = Depends(get_widget_visitor),
    _: None = Depends(enforce_widget_rate_limit),
    session: AsyncSession = Depends(get_session),
) -> Conversation:
    statement = (
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace.id,
            Conversation.end_user_id == visitor.subject,
        )
        .options(selectinload(Conversation.messages))
    )
    conversation = (await session.exec(statement)).first()
    if conversation is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "CONVERSATION_NOT_FOUND",
            "Conversation not found",
        )
    return conversation
