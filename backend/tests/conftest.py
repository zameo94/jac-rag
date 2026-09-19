import os

TEST_ENV = {
    "ENVIRONMENT": "test",
    "DATABASE_URL": "sqlite+aiosqlite://",
    "SQL_ECHO": "false",
    "JWT_SECRET": "test-secret-value-that-is-long-enough-0123456789",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
    "REFRESH_TOKEN_EXPIRE_DAYS": "7",
    "INVITATION_EXPIRE_DAYS": "7",
    "STORAGE_DIR": "./storage-test",
    "MAX_UPLOAD_MB": "20",
    "QDRANT_URL": ":memory:",
    "EMBEDDING_MODEL": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "EMBEDDING_DIM": "384",
    "CHUNK_SIZE": "1000",
    "CHUNK_MAX_SIZE": "1600",
    "CHUNK_OVERLAP": "150",
    "CHUNK_TABLE_CONTEXT": "true",
    "CHUNK_SECTION_CONTEXT": "true",
    "CHUNK_INCLUDE_METADATA": "true",
    "DROP_REPEATED_LAYOUT": "false",
    "PARSER_DEBUG": "false",
    "MIN_CHARS_PER_PAGE": "30",
    "RELEVANCE_THRESHOLD": "0.5",
    "RETRIEVAL_TOP_K": "5",
    "REDIS_URL": "redis://localhost:6379/0",
    "CORS_ORIGINS": "http://localhost:3000",
    "COOKIE_SECURE": "false",
    "COOKIE_SAMESITE": "lax",
}

os.environ.update(TEST_ENV)

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.database import create_engine, create_session_factory, get_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def stub_ingestion(monkeypatch):
    from app.api.v1 import documents as documents_module

    enqueued: list[int] = []

    class _Stub:
        async def kiq(self, document_id):
            enqueued.append(document_id)

    monkeypatch.setattr(documents_module, "ingest_document", _Stub())
    return enqueued


@pytest.fixture
async def sqlite_engine() -> AsyncEngine:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(sqlite_engine):
    async with sqlite_engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    return create_session_factory(sqlite_engine)


@pytest.fixture
async def client(session_factory):
    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()
