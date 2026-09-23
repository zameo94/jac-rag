import shutil
from typing import List

from fastapi import APIRouter, Depends, status
from qdrant_client import AsyncQdrantClient
from sqlalchemy import delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.chat import get_vector_client
from app.core.deps import get_current_membership, get_current_user, require_role
from app.core.errors import api_error
from app.database import get_session
from app.models import (
    ApiKey,
    Conversation,
    Document,
    Invitation,
    Membership,
    Message,
    Setting,
    Workspace,
    User,
)
from app.schemas.membership import MembershipRole
from app.schemas.setting import SettingScope
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceReadWithRole,
    WorkspaceUpdate,
    slugify_value,
)
from app.services import storage
from app.services.rag import vector_store

router = APIRouter()


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Workspace:
    slug = payload.slug or slugify_value(payload.name)
    if not slug:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "INVALID_SLUG",
            "Could not derive a valid slug from the workspace name",
        )

    existing = (await session.exec(select(Workspace).where(Workspace.slug == slug))).first()
    if existing is not None:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "SLUG_ALREADY_TAKEN",
            "A workspace with this slug already exists",
        )

    workspace = Workspace(
        name=payload.name,
        slug=slug,
        default_locale=payload.default_locale,
        answer_mode=payload.answer_mode,
    )
    session.add(workspace)
    await session.flush()

    session.add(
        Membership(
            user_id=current_user.id,
            workspace_id=workspace.id,
            role=MembershipRole.OWNER,
        )
    )

    await session.commit()
    await session.refresh(workspace)
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
async def update_workspace(
    workspace_id: int,
    payload: WorkspaceUpdate,
    _: Membership = Depends(
        require_role(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> Workspace:
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "WORKSPACE_NOT_FOUND", "Workspace not found")

    data = payload.model_dump(exclude_unset=True, exclude_none=True)

    slug = data.get("slug")
    if slug is not None and slug != workspace.slug:
        existing = (
            await session.exec(select(Workspace).where(Workspace.slug == slug))
        ).first()
        if existing is not None and existing.id != workspace_id:
            raise api_error(
                status.HTTP_409_CONFLICT,
                "SLUG_ALREADY_TAKEN",
                "A workspace with this slug already exists",
            )

    for field, value in data.items():
        setattr(workspace, field, value)

    session.add(workspace)
    await session.commit()
    await session.refresh(workspace)
    return workspace


@router.get("", response_model=List[WorkspaceReadWithRole])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[WorkspaceReadWithRole]:
    statement = (
        select(Workspace, Membership.role)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == current_user.id)
        .order_by(Workspace.id)
    )
    rows = (await session.exec(statement)).all()
    return [
        WorkspaceReadWithRole(**workspace.model_dump(), role=role)
        for workspace, role in rows
    ]


@router.get("/{workspace_id}", response_model=WorkspaceRead)
async def get_workspace(
    workspace_id: int,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> Workspace:
    return await session.get(Workspace, workspace_id)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: int,
    _: Membership = Depends(require_role(MembershipRole.OWNER)),
    session: AsyncSession = Depends(get_session),
    client: AsyncQdrantClient = Depends(get_vector_client),
) -> None:
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "WORKSPACE_NOT_FOUND", "Workspace not found")

    conversation_ids = select(Conversation.id).where(
        Conversation.workspace_id == workspace_id
    )
    await session.exec(
        delete(Message).where(Message.conversation_id.in_(conversation_ids))
    )
    await session.exec(delete(Conversation).where(Conversation.workspace_id == workspace_id))
    await session.exec(delete(Document).where(Document.workspace_id == workspace_id))
    await session.exec(delete(ApiKey).where(ApiKey.workspace_id == workspace_id))
    await session.exec(delete(Invitation).where(Invitation.workspace_id == workspace_id))
    await session.exec(delete(Membership).where(Membership.workspace_id == workspace_id))
    await session.exec(
        delete(Setting).where(
            Setting.scope_type == SettingScope.WORKSPACE,
            Setting.scope_id == workspace_id,
        )
    )
    await session.delete(workspace)
    await session.commit()

    await vector_store.delete_collection(client, workspace_id)
    shutil.rmtree(storage.workspace_storage_dir(workspace_id), ignore_errors=True)
