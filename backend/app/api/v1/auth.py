from fastapi import APIRouter, Depends, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.deps import get_current_user
from app.core.errors import api_error
from app.database import get_session
from app.models import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from app.schemas.user import UserRead

router = APIRouter()


def _issue_tokens(user_id: int) -> TokenPair:
    return TokenPair(
        access_token=security.create_access_token(user_id),
        refresh_token=security.create_refresh_token(user_id),
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> User:
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


@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
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

    return _issue_tokens(user.id)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    try:
        user_id = security.decode_token(payload.refresh_token, security.REFRESH_TOKEN_TYPE)
    except security.TokenError:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_REFRESH_TOKEN",
            "The refresh token is invalid or expired",
        )

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_REFRESH_TOKEN",
            "The refresh token is invalid or expired",
        )

    return _issue_tokens(user.id)


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
