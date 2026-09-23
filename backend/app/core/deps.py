from datetime import timedelta

from fastapi import Depends, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.datetimes import ensure_aware_utc, utcnow
from app.core.errors import api_error
from app.database import get_session
from app.models import ApiKey, Membership, Workspace, User
from app.schemas.membership import MembershipRole
from app.services.rate_limit import widget_allowed

bearer_scheme = HTTPBearer(auto_error=False)

ACCESS_COOKIE = "jacrag_access"

LAST_USED_UPDATE_INTERVAL = timedelta(hours=1)


def _extract_access_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    if credentials is not None:
        return credentials.credentials
    return request.cookies.get(ACCESS_COOKIE)


async def authenticate_user(
    session: AsyncSession,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> User:
    token = _extract_access_token(request, credentials)
    if token is None:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "NOT_AUTHENTICATED",
            "Authentication credentials were not provided",
        )

    try:
        user_id = security.decode_token(token, security.ACCESS_TOKEN_TYPE)
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


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    return await authenticate_user(session, request, credentials)


async def load_membership(
    session: AsyncSession,
    user: User,
    workspace_id: int,
) -> Membership:
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "WORKSPACE_NOT_FOUND",
            "Workspace not found",
        )

    membership = (
        await session.exec(
            select(Membership).where(
                Membership.workspace_id == workspace_id,
                Membership.user_id == user.id,
            )
        )
    ).first()

    if membership is None:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "NOT_A_MEMBER",
            "You do not have access to this workspace",
        )

    return membership


async def get_current_membership(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Membership:
    return await load_membership(session, current_user, workspace_id)


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


def ensure_workspace_active(workspace: Workspace) -> None:
    if not workspace.is_active:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "WORKSPACE_INACTIVE",
            "This workspace is disabled",
        )


async def resolve_embed_workspace(session: AsyncSession, embed_key: str | None) -> Workspace:
    if not embed_key:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "EMBED_KEY_REQUIRED",
            "An embed key is required",
        )

    key = (
        await session.exec(
            select(ApiKey).where(ApiKey.key_hash == security.hash_token(embed_key))
        )
    ).first()
    if key is None:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_EMBED_KEY",
            "The embed key is invalid",
        )

    if not key.is_active:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "EMBED_KEY_DISABLED",
            "The embed key is disabled",
        )

    workspace = await session.get(Workspace, key.workspace_id)
    if workspace is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "WORKSPACE_NOT_FOUND",
            "Workspace not found",
        )

    last_used = ensure_aware_utc(key.last_used_at) if key.last_used_at else None
    if last_used is None or utcnow() - last_used > LAST_USED_UPDATE_INTERVAL:
        key.last_used_at = utcnow()
        session.add(key)
        await session.commit()
    return workspace


async def get_embed_workspace(
    x_embed_key: str | None = Header(default=None, alias="X-Embed-Key"),
    session: AsyncSession = Depends(get_session),
) -> Workspace:
    return await resolve_embed_workspace(session, x_embed_key)


async def resolve_widget_visitor(
    workspace: Workspace, visitor_token: str | None
) -> security.VisitorIdentity:
    if not visitor_token:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "VISITOR_TOKEN_REQUIRED",
            "A visitor token is required",
        )

    try:
        identity = security.decode_visitor_token(visitor_token)
    except security.TokenError:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_VISITOR_TOKEN",
            "The visitor token is invalid or expired",
        )

    if identity.workspace_id != workspace.id:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "VISITOR_WORKSPACE_MISMATCH",
            "The visitor token does not belong to this workspace",
        )

    return identity


async def get_widget_visitor(
    x_visitor_token: str | None = Header(default=None, alias="X-Visitor-Token"),
    workspace: Workspace = Depends(get_embed_workspace),
) -> security.VisitorIdentity:
    return await resolve_widget_visitor(workspace, x_visitor_token)


async def enforce_widget_rate_limit(
    x_embed_key: str | None = Header(default=None, alias="X-Embed-Key"),
    workspace: Workspace = Depends(get_embed_workspace),
) -> None:
    if not await widget_allowed(x_embed_key, workspace.id):
        raise api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "RATE_LIMITED",
            "Too many requests",
        )
