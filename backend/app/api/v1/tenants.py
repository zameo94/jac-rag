from typing import List

from fastapi import APIRouter, Depends, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.deps import get_current_membership, get_current_user
from app.core.errors import api_error
from app.database import get_session
from app.models import Membership, Tenant, User
from app.schemas.membership import MembershipRole
from app.schemas.tenant import TenantCreate, TenantRead, slugify_value

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
