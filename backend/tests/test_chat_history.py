import pytest
from qdrant_client import AsyncQdrantClient
from sqlmodel import select

from app.api.v1 import chat as chat_module
from app.main import app
from app.models import Conversation, Membership, Message
from app.schemas.membership import MembershipRole
from app.services.llm import LLMProvider, LLMProviderError, LLMResponse
from app.services.rag import embeddings, vector_store
from app.services.rag.chat.conversations import make_title
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


async def index_texts(qdrant, tenant_id: int, texts) -> None:
    vectors = await embeddings.embed_texts(texts)
    await vector_store.upsert_chunks(
        qdrant,
        tenant_id,
        1,
        "doc.md",
        [(index, text) for index, text in enumerate(texts)],
        vectors,
    )


def patch_provider(monkeypatch, provider) -> None:
    async def build(session, tenant_id, provider_id, model=None):
        return provider, "test-model"

    monkeypatch.setattr("app.services.rag.chat.prepare.build_provider", build)


def test_make_title_collapses_whitespace():
    assert make_title("  Ciao \n  mondo  ") == "Ciao mondo"


async def test_chat_creates_conversation_and_messages(
    client, qdrant, session_factory, monkeypatch
):
    headers = await register_and_login(client, "history-owner@example.com")
    tenant_id = await create_tenant(client, headers)
    owner_id = await user_id_for(client, headers)
    await index_texts(qdrant, tenant_id, [CHUNK_TEXT])
    patch_provider(monkeypatch, FakeProvider())

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat", json={"message": QUERY}, headers=headers
    )

    assert response.status_code == 200
    async with session_factory() as session:
        conversations = (await session.exec(select(Conversation))).all()
        messages = (await session.exec(select(Message).order_by(Message.id))).all()

    assert len(conversations) == 1
    assert conversations[0].user_id == owner_id
    assert conversations[0].end_user_id is None
    assert conversations[0].title == QUERY
    assert [m.role.value for m in messages] == ["user", "assistant"]
    assert messages[0].content == QUERY
    assert messages[1].content == "Risposta di prova"
    assert messages[1].grounded is True
    assert messages[1].sources


async def test_chat_reuses_conversation_and_sends_history(
    client, qdrant, session_factory, monkeypatch
):
    headers = await register_and_login(client, "history-reuse@example.com")
    tenant_id = await create_tenant(client, headers)
    await index_texts(qdrant, tenant_id, [CHUNK_TEXT])
    provider = FakeProvider()
    patch_provider(monkeypatch, provider)

    first = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat", json={"message": QUERY}, headers=headers
    )
    async with session_factory() as session:
        conversation_id = (await session.exec(select(Conversation))).one().id

    second = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat",
        json={"message": QUERY, "conversation_id": conversation_id},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert [m.role.value for m in provider.calls[1]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    async with session_factory() as session:
        conversations = (await session.exec(select(Conversation))).all()
        messages = (await session.exec(select(Message))).all()
    assert len(conversations) == 1
    assert len(messages) == 4


async def test_chat_rejects_another_actors_conversation(
    client, qdrant, session_factory, monkeypatch
):
    owner_headers = await register_and_login(client, "history-a@example.com")
    tenant_id = await create_tenant(client, owner_headers)
    await index_texts(qdrant, tenant_id, [CHUNK_TEXT])
    patch_provider(monkeypatch, FakeProvider())
    await client.post(
        f"/api/v1/tenants/{tenant_id}/chat", json={"message": QUERY}, headers=owner_headers
    )
    async with session_factory() as session:
        conversation_id = (await session.exec(select(Conversation))).one().id

    other_headers = await register_and_login(client, "history-b@example.com")
    other_id = await user_id_for(client, other_headers)
    async with session_factory() as session:
        session.add(
            Membership(
                user_id=other_id, tenant_id=tenant_id, role=MembershipRole.MEMBER
            )
        )
        await session.commit()

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat",
        json={"message": "ciao", "conversation_id": conversation_id},
        headers=other_headers,
    )

    assert response.status_code == 404
    assert response.json()["code"] == "CONVERSATION_NOT_FOUND"


async def test_chat_strict_refusal_is_persisted(
    client, qdrant, session_factory, monkeypatch
):
    headers = await register_and_login(client, "history-refusal@example.com")
    tenant_id = await create_tenant(client, headers)
    provider = FakeProvider()
    patch_provider(monkeypatch, provider)

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat",
        json={"message": "Domanda senza contesto"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["grounded"] is False
    assert provider.calls == []
    async with session_factory() as session:
        messages = (await session.exec(select(Message).order_by(Message.id))).all()
    assert [m.role.value for m in messages] == ["user", "assistant"]
    assert messages[1].grounded is False
    assert messages[1].sources == []


async def test_chat_provider_failure_persists_error_message(
    client, qdrant, session_factory, monkeypatch
):
    headers = await register_and_login(client, "history-error@example.com")
    tenant_id = await create_tenant(client, headers)
    await index_texts(qdrant, tenant_id, [CHUNK_TEXT])
    patch_provider(monkeypatch, FailingProvider())

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat", json={"message": QUERY}, headers=headers
    )

    assert response.status_code == 503
    assert response.json()["code"] == "LLM_UNAVAILABLE"
    async with session_factory() as session:
        messages = (await session.exec(select(Message).order_by(Message.id))).all()
    assert [m.role.value for m in messages] == ["user", "assistant"]
    assert messages[1].error_code == "LLM_UNAVAILABLE"


async def test_history_is_limited_by_setting(
    client, qdrant, session_factory, monkeypatch
):
    from app.core.config import get_settings

    monkeypatch.setenv("CHAT_HISTORY_LIMIT", "2")
    get_settings.cache_clear()
    headers = await register_and_login(client, "history-limit@example.com")
    tenant_id = await create_tenant(client, headers)
    await index_texts(qdrant, tenant_id, [CHUNK_TEXT])
    provider = FakeProvider()
    patch_provider(monkeypatch, provider)

    await client.post(
        f"/api/v1/tenants/{tenant_id}/chat", json={"message": QUERY}, headers=headers
    )
    async with session_factory() as session:
        conversation_id = (await session.exec(select(Conversation))).one().id

    for _ in range(3):
        await client.post(
            f"/api/v1/tenants/{tenant_id}/chat",
            json={"message": QUERY, "conversation_id": conversation_id},
            headers=headers,
        )

    assert len(provider.calls[-1]) == 2 + 2


async def test_history_skips_failed_assistant_messages(
    client, qdrant, session_factory, monkeypatch
):
    headers = await register_and_login(client, "history-skip-errors@example.com")
    tenant_id = await create_tenant(client, headers)
    await index_texts(qdrant, tenant_id, [CHUNK_TEXT])

    patch_provider(monkeypatch, FailingProvider())
    first = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat", json={"message": QUERY}, headers=headers
    )
    async with session_factory() as session:
        conversation_id = (await session.exec(select(Conversation))).one().id

    provider = FakeProvider()
    patch_provider(monkeypatch, provider)
    second = await client.post(
        f"/api/v1/tenants/{tenant_id}/chat",
        json={"message": QUERY, "conversation_id": conversation_id},
        headers=headers,
    )

    assert first.status_code == 503
    assert second.status_code == 200
    assert [m.role.value for m in provider.calls[0]] == ["system", "user", "user"]
