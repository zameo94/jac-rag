from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings


def create_engine(
    database_url: str,
    echo: bool = False,
    *,
    pool_size: int | None = None,
    max_overflow: int | None = None,
    pool_timeout: int | None = None,
) -> AsyncEngine:
    kwargs: dict = {}
    if database_url.startswith("sqlite+aiosqlite"):
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        if pool_size is not None:
            kwargs["pool_size"] = pool_size
        if max_overflow is not None:
            kwargs["max_overflow"] = max_overflow
        if pool_timeout is not None:
            kwargs["pool_timeout"] = pool_timeout
    return create_async_engine(database_url, echo=echo, **kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


settings = get_settings()
engine = create_engine(
    settings.database_url,
    echo=settings.sql_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
)
async_session_factory = create_session_factory(engine)


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Open one session for a bounded unit of work and close it on exit.

    Streaming routes use this instead of the request-scoped dependency so no
    connection stays checked out while the response is being streamed.
    """
    async with async_session_factory() as session:
        yield session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with session_scope() as session:
        yield session
