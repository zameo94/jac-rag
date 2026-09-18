from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings


def create_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    kwargs: dict = {}
    if database_url.startswith("sqlite+aiosqlite"):
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_async_engine(database_url, echo=echo, **kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


settings = get_settings()
engine = create_engine(settings.database_url, echo=settings.sql_echo)
async_session_factory = create_session_factory(engine)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
