from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app import database
from app.database import create_engine, create_session_factory
from app.models import User
from app.schemas.user import UserCreate


async def create_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)


async def test_create_engine_returns_async_engine(sqlite_engine):
    assert isinstance(sqlite_engine, AsyncEngine)


async def test_session_factory_yields_sqlmodel_async_session(sqlite_engine):
    factory = create_session_factory(sqlite_engine)

    async with factory() as session:
        assert isinstance(session, SQLModelAsyncSession)


async def test_session_can_execute_a_query(sqlite_engine):
    await create_tables(sqlite_engine)
    factory = create_session_factory(sqlite_engine)

    async with factory() as session:
        users = (await session.exec(select(User))).all()

    assert users == []


async def test_get_session_yields_usable_session(sqlite_engine, monkeypatch):
    await create_tables(sqlite_engine)
    monkeypatch.setattr(
        database,
        "async_session_factory",
        create_session_factory(sqlite_engine),
    )

    generator = database.get_session()
    session = await generator.__anext__()

    assert isinstance(session, SQLModelAsyncSession)
    assert (await session.exec(select(User))).all() == []

    await generator.aclose()


async def test_user_model_round_trip(sqlite_engine):
    await create_tables(sqlite_engine)
    factory = create_session_factory(sqlite_engine)
    payload = UserCreate(email="Test@Example.com", locale="it")

    async with factory() as session:
        session.add(
            User(
                email=payload.email,
                locale=payload.locale,
                password_hash="hashed-password",
            )
        )
        await session.commit()

    async with factory() as session:
        user = (await session.exec(select(User))).one()

    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.locale == "it"
    assert user.is_active is True
    assert user.password_hash == "hashed-password"
    assert user.created_at is not None
    assert user.updated_at is not None
