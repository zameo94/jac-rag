import os

TEST_ENV = {
    "ENVIRONMENT": "test",
    "DATABASE_URL": "sqlite+aiosqlite://",
    "DB_POOL_SIZE": "5",
    "DB_MAX_OVERFLOW": "10",
    "DB_POOL_TIMEOUT": "30",
    "SQL_ECHO": "false",
    "JWT_SECRET": "test-secret-value-that-is-long-enough-0123456789",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
    "REFRESH_TOKEN_EXPIRE_DAYS": "7",
    "SESSION_IDLE_TIMEOUT_MINUTES": "60",
    "AUTH_LOGIN_RATE_LIMIT_PER_MINUTE": "0",
    "AUTH_REGISTER_RATE_LIMIT_PER_MINUTE": "0",
    "AUTH_REFRESH_RATE_LIMIT_PER_MINUTE": "0",
    "AUTH_ACCEPT_RATE_LIMIT_PER_MINUTE": "0",
    "INVITATION_EXPIRE_DAYS": "7",
    "VISITOR_TOKEN_EXPIRE_DAYS": "30",
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
    "HYBRID_ENABLED": "false",
    "RRF_K": "60",
    "RERANK_ENABLED": "false",
    "RERANK_MODEL": "jinaai/jina-reranker-v2-base-multilingual",
    "RERANK_CANDIDATES": "30",
    "RERANK_BATCH_SIZE": "4",
    "RERANK_MODE": "on_demand",
    "CHAT_CONTEXT_K": "5",
    "CHAT_HISTORY_LIMIT": "10",
    "CHAT_RETENTION_DAYS": "30",
    "WIDGET_RATE_LIMIT_PER_MINUTE": "0",
    "OCR_ENABLED": "false",
    "OCR_DPI": "200",
    "OCR_MIN_CONFIDENCE": "0.5",
    "OCR_IMAGE_DOMINANCE_RATIO": "0.6",
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "OLLAMA_DEFAULT_MODEL": "llama3.2",
    "LLM_DEFAULT_PROVIDER": "ollama",
    "ENCRYPTION_KEY": "o4MfFKmB8dDuat5Ky6r-gbDdX6ClT9BXhAp85ZVC9xk=",
    "EXTERNAL_API_ENABLED": "false",
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

from app import database  # noqa: E402
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
async def client(session_factory, monkeypatch):
    monkeypatch.setattr(database, "async_session_factory", session_factory)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()
