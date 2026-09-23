from typing import List

from fastapi import APIRouter, Depends, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.deps import require_role
from app.core.errors import api_error
from app.database import get_session
from app.models import ApiKey, Membership
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead, ApiKeyUpdate
from app.schemas.membership import MembershipRole

router = APIRouter()

MANAGERS = (MembershipRole.OWNER, MembershipRole.ADMIN)


@router.post(
    "/{workspace_id}/api-keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    workspace_id: int,
    payload: ApiKeyCreate,
    membership: Membership = Depends(require_role(*MANAGERS)),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyCreated:
    plaintext = security.generate_embed_key()
    key = ApiKey(
        workspace_id=workspace_id,
        name=payload.name,
        prefix=security.embed_key_prefix(plaintext),
        key_hash=security.hash_token(plaintext),
        created_by=membership.user_id,
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return ApiKeyCreated(
        id=key.id,
        workspace_id=key.workspace_id,
        name=key.name,
        prefix=key.prefix,
        is_active=key.is_active,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
        key=plaintext,
    )


@router.get("/{workspace_id}/api-keys", response_model=List[ApiKeyRead])
async def list_api_keys(
    workspace_id: int,
    membership: Membership = Depends(require_role(*MANAGERS)),
    session: AsyncSession = Depends(get_session),
) -> List[ApiKey]:
    statement = (
        select(ApiKey).where(ApiKey.workspace_id == workspace_id).order_by(ApiKey.id.desc())
    )
    return (await session.exec(statement)).all()


@router.patch("/{workspace_id}/api-keys/{key_id}", response_model=ApiKeyRead)
async def update_api_key(
    workspace_id: int,
    key_id: int,
    payload: ApiKeyUpdate,
    membership: Membership = Depends(require_role(*MANAGERS)),
    session: AsyncSession = Depends(get_session),
) -> ApiKey:
    key = await session.get(ApiKey, key_id)
    if key is None or key.workspace_id != workspace_id:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "API_KEY_NOT_FOUND",
            "API key not found",
        )

    key.is_active = payload.is_active
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return key
