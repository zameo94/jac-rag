from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.errors import api_error
from app.core.http import client_ip
from app.database import get_session
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, UpdateLocaleRequest
from app.schemas.user import UserRead
from app.services.rate_limit import auth_allowed

router = APIRouter()
settings = get_settings()

ACCESS_COOKIE = "jacrag_access"
REFRESH_COOKIE = "jacrag_refresh"


async def _enforce_rate_limit(scope: str, request: Request, email: str | None = None) -> None:
    if not await auth_allowed(scope, client_ip(request), email):
        raise api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "RATE_LIMITED",
            "Too many attempts, try again later",
        )


def _set_auth_cookies(
    response: Response, user_id: int, session_started_at: datetime | None = None
) -> None:
    started_at = session_started_at or datetime.now(timezone.utc)
    access_token = security.create_access_token(user_id)
    refresh_token = security.create_refresh_token(user_id, session_started_at=started_at)
    refresh_lifetime = security.refresh_token_lifetime(started_at)
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "domain": settings.cookie_domain,
    }
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=int(timedelta(minutes=settings.access_token_expire_minutes).total_seconds()),
        path="/",
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=max(int(refresh_lifetime.total_seconds()), 0),
        path="/",
        **common,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=settings.cookie_domain)
    response.delete_cookie(REFRESH_COOKIE, path="/", domain=settings.cookie_domain)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> User:
    await _enforce_rate_limit("register", request, payload.email)
    existing = (await session.exec(select(User).where(User.email == payload.email))).first()
    if existing is not None:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "EMAIL_ALREADY_REGISTERED",
            "An account with this email already exists",
        )

    user = User(
        email=payload.email,
        locale=payload.locale,
        password_hash=security.hash_password(payload.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/login", response_model=UserRead)
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> User:
    await _enforce_rate_limit("login", request, payload.email)
    user = (await session.exec(select(User).where(User.email == payload.email))).first()
    if user is None or not security.verify_password(payload.password, user.password_hash):
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_CREDENTIALS",
            "Invalid email or password",
        )

    if not user.is_active:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "ACCOUNT_DISABLED",
            "The user account is disabled",
        )

    _set_auth_cookies(response, user.id)
    return user


@router.post("/refresh", response_model=UserRead)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> User:
    await _enforce_rate_limit("refresh", request)
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_REFRESH_TOKEN",
            "The refresh token is missing or invalid",
        )

    try:
        identity = security.decode_refresh_token(token)
    except security.TokenError:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_REFRESH_TOKEN",
            "The refresh token is invalid or expired",
        )

    user = await session.get(User, identity.user_id)
    if user is None or not user.is_active:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_REFRESH_TOKEN",
            "The refresh token is invalid or expired",
        )

    _set_auth_cookies(response, user.id, identity.session_started_at)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UpdateLocaleRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    current_user.locale = payload.locale
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return current_user
