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
    Tenant,
    User,
)
from app.schemas.membership import MembershipRole
from app.schemas.setting import SettingScope
from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate, slugify_value
from app.services import storage
from app.services.rag import vector_store

router = APIRouter()


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Tenant:
    slug = payload.slug or slugify_value(payload.name)
    if not slug:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "INVALID_SLUG",
            "Could not derive a valid slug from the tenant name",
        )

    existing = (await session.exec(select(Tenant).where(Tenant.slug == slug))).first()
    if existing is not None:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "SLUG_ALREADY_TAKEN",
            "A tenant with this slug already exists",
        )

    tenant = Tenant(
        name=payload.name,
        slug=slug,
        default_locale=payload.default_locale,
        answer_mode=payload.answer_mode,
    )
    session.add(tenant)
    await session.flush()

    session.add(
        Membership(
            user_id=current_user.id,
            tenant_id=tenant.id,
            role=MembershipRole.OWNER,
        )
    )

    await session.commit()
    await session.refresh(tenant)
    return tenant


@router.patch("/{tenant_id}", response_model=TenantRead)
async def update_tenant(
    tenant_id: int,
    payload: TenantUpdate,
    _: Membership = Depends(
        require_role(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> Tenant:
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "TENANT_NOT_FOUND", "Tenant not found")

    data = payload.model_dump(exclude_unset=True, exclude_none=True)

    slug = data.get("slug")
    if slug is not None and slug != tenant.slug:
        existing = (
            await session.exec(select(Tenant).where(Tenant.slug == slug))
        ).first()
        if existing is not None and existing.id != tenant_id:
            raise api_error(
                status.HTTP_409_CONFLICT,
                "SLUG_ALREADY_TAKEN",
                "A tenant with this slug already exists",
            )

    for field, value in data.items():
        setattr(tenant, field, value)

    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)
    return tenant


@router.get("", response_model=List[TenantRead])
async def list_tenants(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[Tenant]:
    statement = (
        select(Tenant)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .where(Membership.user_id == current_user.id)
        .order_by(Tenant.id)
    )
    return (await session.exec(statement)).all()


@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(
    tenant_id: int,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> Tenant:
    return await session.get(Tenant, tenant_id)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: int,
    _: Membership = Depends(require_role(MembershipRole.OWNER)),
    session: AsyncSession = Depends(get_session),
    client: AsyncQdrantClient = Depends(get_vector_client),
) -> None:
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "TENANT_NOT_FOUND", "Tenant not found")

    conversation_ids = select(Conversation.id).where(
        Conversation.tenant_id == tenant_id
    )
    await session.exec(
        delete(Message).where(Message.conversation_id.in_(conversation_ids))
    )
    await session.exec(delete(Conversation).where(Conversation.tenant_id == tenant_id))
    await session.exec(delete(Document).where(Document.tenant_id == tenant_id))
    await session.exec(delete(ApiKey).where(ApiKey.tenant_id == tenant_id))
    await session.exec(delete(Invitation).where(Invitation.tenant_id == tenant_id))
    await session.exec(delete(Membership).where(Membership.tenant_id == tenant_id))
    await session.exec(
        delete(Setting).where(
            Setting.scope_type == SettingScope.TENANT,
            Setting.scope_id == tenant_id,
        )
    )
    await session.delete(tenant)
    await session.commit()

    await vector_store.delete_collection(client, tenant_id)
    shutil.rmtree(storage.tenant_storage_dir(tenant_id), ignore_errors=True)
