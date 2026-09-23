from datetime import timedelta

from fastapi import APIRouter, Depends, Request, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.datetimes import ensure_aware_utc, utcnow
from app.core.deps import get_current_user, require_role
from app.core.errors import api_error
from app.core.http import client_ip
from app.database import get_session
from app.models import Invitation, Membership, Workspace, User
from app.schemas.invitation import InvitationCreate, InvitationCreated
from app.schemas.membership import MembershipRead, MembershipRole
from app.services.rate_limit import auth_allowed

router = APIRouter()
settings = get_settings()


@router.post(
    "/workspaces/{workspace_id}/invitations",
    response_model=InvitationCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    workspace_id: int,
    payload: InvitationCreate,
    membership: Membership = Depends(require_role(MembershipRole.OWNER, MembershipRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> InvitationCreated:
    invited_user = (await session.exec(select(User).where(User.email == payload.email))).first()
    if invited_user is not None:
        already_member = (
            await session.exec(
                select(Membership).where(
                    Membership.workspace_id == workspace_id,
                    Membership.user_id == invited_user.id,
                )
            )
        ).first()
        if already_member is not None:
            raise api_error(
                status.HTTP_409_CONFLICT,
                "ALREADY_A_MEMBER",
                "This user is already a member of the workspace",
            )

    pending = (
        await session.exec(
            select(Invitation).where(
                Invitation.workspace_id == workspace_id,
                Invitation.email == payload.email,
                Invitation.accepted_at.is_(None),
            )
        )
    ).first()
    if pending is not None and ensure_aware_utc(pending.expires_at) > utcnow():
        raise api_error(
            status.HTTP_409_CONFLICT,
            "INVITATION_ALREADY_PENDING",
            "A pending invitation already exists for this email",
        )

    token = security.generate_invitation_token()
    invitation = Invitation(
        workspace_id=workspace_id,
        email=payload.email,
        role=payload.role,
        token_hash=security.hash_token(token),
        expires_at=utcnow() + timedelta(days=settings.invitation_expire_days),
        created_by=membership.user_id,
    )
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)

    return InvitationCreated(
        id=invitation.id,
        workspace_id=invitation.workspace_id,
        email=invitation.email,
        role=invitation.role,
        token=token,
        expires_at=invitation.expires_at,
    )


@router.post("/invitations/{token}/accept", response_model=MembershipRead)
async def accept_invitation(
    request: Request,
    token: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Membership:
    if not await auth_allowed("accept", client_ip(request)):
        raise api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "RATE_LIMITED",
            "Too many attempts, try again later",
        )
    invitation = (
        await session.exec(
            select(Invitation).where(Invitation.token_hash == security.hash_token(token))
        )
    ).first()

    if invitation is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "INVITATION_NOT_FOUND",
            "The invitation does not exist",
        )

    if invitation.accepted_at is not None:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "INVITATION_ALREADY_ACCEPTED",
            "The invitation has already been accepted",
        )

    if ensure_aware_utc(invitation.expires_at) < utcnow():
        raise api_error(
            status.HTTP_410_GONE,
            "INVITATION_EXPIRED",
            "The invitation has expired",
        )

    if invitation.email != current_user.email:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "INVITATION_EMAIL_MISMATCH",
            "The invitation was issued to a different email address",
        )

    workspace = await session.get(Workspace, invitation.workspace_id)
    if workspace is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "WORKSPACE_NOT_FOUND",
            "Workspace not found",
        )

    existing_membership = (
        await session.exec(
            select(Membership).where(
                Membership.workspace_id == invitation.workspace_id,
                Membership.user_id == current_user.id,
            )
        )
    ).first()
    if existing_membership is not None:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "ALREADY_A_MEMBER",
            "You are already a member of this workspace",
        )

    membership = Membership(
        user_id=current_user.id,
        workspace_id=invitation.workspace_id,
        role=invitation.role,
    )
    session.add(membership)
    invitation.accepted_at = utcnow()
    session.add(invitation)
    await session.commit()
    await session.refresh(membership)
    return membership
