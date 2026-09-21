import pytest
from qdrant_client import AsyncQdrantClient

from app.api.v1 import chat as chat_module
from app.main import app
from app.models import Setting, Tenant
from app.schemas.setting import SettingScope
from app.schemas.tenant import AnswerMode
from app.services.llm import LLMProvider, LLMProviderError, LLMResponse
from app.services.rag import embeddings, vector_store
from tests.helpers import register_and_login, user_id_for

CHUNK_TEXT = "Il colore preferito della macchina aziendale e il blu."
QUERY = "Qual e il colore preferito della macchina aziendale?"


class FakeProvider(LLMProvider):
    name = "ollama"

    def __init__(self, reply: str = "Risposta di prova") -> None:
        self.reply = reply
        self.calls: list[list] = []

    async def generate(self, messages, *, model=None, temperature=0.0):
        self.calls.append(list(messages))
        return LLMResponse(content=self.reply, model=model or "llama3.2", provider=self.name)

    async def stream(self, messages, *, model=None, temperature=0.0):
        yield self.reply


class FailingProvider(FakeProvider):
    async def generate(self, messages, *, model=None, temperature=0.0):
        raise LLMProviderError("LLM_UNAVAILABLE", "ollama is down")


def patch_provider(monkeypatch, provider):
    async def build(session, tenant_id, provider_id, model=None):
        return provider, "test-model"

    monkeypatch.setattr("app.services.rag.chat.prepare.build_provider", build)


@pytest.fixture
async def qdrant():
    client = AsyncQdrantClient(":memory:")

    async def override():
        yield client

    app.dependency_overrides[chat_module.get_vector_client] = override
    yield client
    await client.close()
    app.dependency_overrides.pop(chat_module.get_vector_client, None)


async def create_tenant(client, headers, name: str = "Acme") -> int:
    response = await client.post("/api/v1/tenants", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def index_texts(qdrant, tenant_id: int, texts, document_id: int = 1, filename: str = "doc.md"):
    vectors = embeddings.embed_texts(texts)
    await vector_store.upsert_chunks(
        qdrant,
        tenant_id,
        document_id,
        filename,
        [(index, text) for index, text in enumerate(texts)],
        vectors,
    )


async def test_chat_grounded_returns_answer_and_sources(client, qdrant, monkeypatch):
    headers = await register_and_login(client, "chat-owner@example.com")
    tenant_id = await create_tenant(client, headers)
    await index_texts(qdrant, tenant_id, [CHUNK_TEXT])

    fake = FakeProvider()
    created: list[str] = []

    async def build(session, tenant_id, provider_id, model=None):
        created.append(provider_id)
        return fake, "llama3.2"

    monkeypatch.setattr("app.services.rag.chat.prepare.build_provider", build)

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat",
        json={"message": QUERY},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Risposta di prova"
    assert body["provider"] == "ollama"
    assert body["model"]
    assert body["grounded"] is True
    assert len(body["sources"]) == 1
    assert body["sources"][0]["filename"] == "doc.md"
    assert body["sources"][0]["chunk_index"] == 0
    assert created == ["ollama"]
    assert len(fake.calls) == 1


async def test_chat_strict_refuses_without_context(client, qdrant, monkeypatch):
    headers = await register_and_login(client, "chat-strict@example.com")
    tenant_id = await create_tenant(client, headers)

    fake = FakeProvider()
    patch_provider(monkeypatch, fake)

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat",
        json={"message": "Domanda senza alcun contesto disponibile"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is False
    assert body["sources"] == []
    assert body["answer"]
    assert fake.calls == []


async def test_chat_assistive_answers_without_context(
    client, qdrant, monkeypatch, session_factory
):
    headers = await register_and_login(client, "chat-assistive@example.com")
    tenant_id = await create_tenant(client, headers)

    async with session_factory() as session:
        tenant = await session.get(Tenant, tenant_id)
        tenant.answer_mode = AnswerMode.ASSISTIVE
        session.add(tenant)
        await session.commit()

    fake = FakeProvider(reply="Risposta assistiva")
    patch_provider(monkeypatch, fake)

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat",
        json={"message": "Domanda libera"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Risposta assistiva"
    assert body["grounded"] is False
    assert body["sources"] == []
    assert len(fake.calls) == 1


async def test_chat_rejects_disabled_provider_selection(
    client, qdrant, session_factory
):
    headers = await register_and_login(client, "chat-disabled@example.com")
    tenant_id = await create_tenant(client, headers)
    user_id = await user_id_for(client, headers)

    async with session_factory() as session:
        session.add(
            Setting(
                scope_type=SettingScope.USER,
                scope_id=user_id,
                type="llm",
                key="selected_provider",
                value="external_api",
            )
        )
        await session.commit()

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat",
        json={"message": "ciao"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "PROVIDER_NOT_AVAILABLE"


async def test_chat_provider_failure_returns_503(client, qdrant, monkeypatch):
    headers = await register_and_login(client, "chat-fail@example.com")
    tenant_id = await create_tenant(client, headers)
    await index_texts(qdrant, tenant_id, [CHUNK_TEXT])
    patch_provider(monkeypatch, FailingProvider())

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat",
        json={"message": QUERY},
        headers=headers,
    )

    assert response.status_code == 503
    assert response.json()["code"] == "LLM_UNAVAILABLE"


async def test_chat_requires_authentication(client, qdrant):
    response = await client.post("/api/v1/tenants/1/chat", json={"message": "ciao"})

    assert response.status_code == 401


async def test_chat_rejects_non_member(client, qdrant):
    owner_headers = await register_and_login(client, "chat-owner2@example.com")
    tenant_id = await create_tenant(client, owner_headers)
    other_headers = await register_and_login(client, "chat-other@example.com")

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat",
        json={"message": "ciao"},
        headers=other_headers,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "NOT_A_MEMBER"
