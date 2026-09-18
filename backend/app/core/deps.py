from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.errors import api_error
from app.database import get_session
from app.models import Membership, Tenant, User
from app.schemas.membership import MembershipRole

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "NOT_AUTHENTICATED",
            "Authentication credentials were not provided",
        )

    try:
        user_id = security.decode_token(credentials.credentials, security.ACCESS_TOKEN_TYPE)
    except security.TokenError:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_TOKEN",
            "The access token is invalid or expired",
        )

    user = await session.get(User, user_id)
    if user is None:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_TOKEN",
            "The access token is invalid or expired",
        )

    if not user.is_active:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "ACCOUNT_DISABLED",
            "The user account is disabled",
        )

    return user


async def get_current_membership(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Membership:
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "TENANT_NOT_FOUND",
            "Tenant not found",
        )

    membership = (
        await session.exec(
            select(Membership).where(
                Membership.tenant_id == tenant_id,
                Membership.user_id == current_user.id,
            )
        )
    ).first()

    if membership is None:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "NOT_A_MEMBER",
            "You do not have access to this tenant",
        )

    return membership


def require_role(*roles: MembershipRole):
    async def dependency(
        membership: Membership = Depends(get_current_membership),
    ) -> Membership:
        if membership.role not in roles:
            raise api_error(
                status.HTTP_403_FORBIDDEN,
                "INSUFFICIENT_ROLE",
                "Your role does not allow this action",
            )
        return membership

    return dependency
