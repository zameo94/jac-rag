from typing import List

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.deps import get_current_membership, require_role
from app.core.errors import api_error
from app.database import get_session
from app.models import Membership, User
from app.schemas.membership import (
    MemberRead,
    MemberUpdate,
    MembershipRead,
    MembershipRole,
)

router = APIRouter()


def _to_member(membership: Membership, user: User) -> MemberRead:
    return MemberRead(
        id=membership.id,
        user_id=membership.user_id,
        workspace_id=membership.workspace_id,
        role=membership.role,
        email=user.email,
        created_at=membership.created_at,
    )


@router.get("/{workspace_id}/me", response_model=MembershipRead)
async def my_membership(
    membership: Membership = Depends(get_current_membership),
) -> Membership:
    return membership


@router.get("/{workspace_id}/members", response_model=List[MemberRead])
async def list_members(
    workspace_id: int,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> List[MemberRead]:
    statement = (
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id == workspace_id)
        .order_by(Membership.id)
    )
    rows = (await session.exec(statement)).all()
    return [_to_member(member, user) for member, user in rows]


@router.patch("/{workspace_id}/members/{user_id}", response_model=MemberRead)
async def update_member_role(
    workspace_id: int,
    user_id: int,
    payload: MemberUpdate,
    membership: Membership = Depends(require_role(MembershipRole.OWNER, MembershipRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> MemberRead:
    target = (
        await session.exec(
            select(Membership).where(
                Membership.workspace_id == workspace_id,
                Membership.user_id == user_id,
            )
        )
    ).first()

    if target is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "MEMBER_NOT_FOUND",
            "The user is not a member of this workspace",
        )

    if target.role is MembershipRole.OWNER:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "CANNOT_MODIFY_OWNER",
            "The owner role cannot be modified",
        )

    target.role = payload.role
    session.add(target)
    await session.commit()
    await session.refresh(target)

    user = await session.get(User, target.user_id)
    return _to_member(target, user)


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: int,
    user_id: int,
    membership: Membership = Depends(require_role(MembershipRole.OWNER, MembershipRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if user_id == membership.user_id:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "CANNOT_REMOVE_SELF",
            "You cannot remove yourself from the workspace",
        )

    target = (
        await session.exec(
            select(Membership).where(
                Membership.workspace_id == workspace_id,
                Membership.user_id == user_id,
            )
        )
    ).first()

    if target is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "MEMBER_NOT_FOUND",
            "The user is not a member of this workspace",
        )

    if target.role is MembershipRole.OWNER:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "CANNOT_REMOVE_OWNER",
            "The owner cannot be removed from the workspace",
        )

    await session.delete(target)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
