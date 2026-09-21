from typing import List

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.deps import require_role
from app.core.errors import api_error
from app.database import get_session
from app.models import Conversation, Membership
from app.schemas.conversation import ConversationDetail, ConversationRead
from app.schemas.membership import MembershipRole

router = APIRouter()

READERS = (MembershipRole.OWNER, MembershipRole.ADMIN)


@router.get("/{tenant_id}/conversations", response_model=List[ConversationRead])
async def list_conversations(
    tenant_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    membership: Membership = Depends(require_role(*READERS)),
    session: AsyncSession = Depends(get_session),
) -> List[Conversation]:
    statement = (
        select(Conversation)
        .where(Conversation.tenant_id == tenant_id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list((await session.exec(statement)).all())


@router.get(
    "/{tenant_id}/conversations/{conversation_id}",
    response_model=ConversationDetail,
)
async def get_conversation(
    tenant_id: int,
    conversation_id: int,
    membership: Membership = Depends(require_role(*READERS)),
    session: AsyncSession = Depends(get_session),
) -> Conversation:
    statement = (
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id,
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


@router.delete(
    "/{tenant_id}/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    tenant_id: int,
    conversation_id: int,
    membership: Membership = Depends(require_role(*READERS)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != tenant_id:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "CONVERSATION_NOT_FOUND",
            "Conversation not found",
        )

    await session.delete(conversation)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
