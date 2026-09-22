import json

import pytest
from qdrant_client import AsyncQdrantClient
from sqlmodel import select

from app.api.v1 import chat as chat_module
from app.core import security
from app.main import app
from app.models import ApiKey, Conversation, Message
from app.services.llm import LLMProvider, LLMResponse
from app.services.rag import embeddings, vector_store
from tests.helpers import register_and_login, user_id_for

CHUNK_TEXT = "Il colore preferito della macchina aziendale e il blu."
QUERY = "Qual e il colore preferito della macchina aziendale?"


def parse_events(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        name = next(
            (line[len("event: ") :] for line in lines if line.startswith("event: ")),
            None,
        )
        data = "\n".join(
            line[len("data: ") :] for line in lines if line.startswith("data: ")
        )
        if name is not None:
            events.append((name, json.loads(data) if data else {}))
    return events


class FakeProvider(LLMProvider):
    name = "ollama"

    def __init__(self) -> None:
        self.closed = False

    async def generate(self, messages, *, model=None, temperature=0.0):
        return LLMResponse(content="Risposta widget", model=model or "m", provider=self.name)

    async def stream(self, messages, *, model=None, temperature=0.0):
        yield "Risposta"
        yield " widget"

    async def aclose(self) -> None:
        self.closed = True


def patch_provider(monkeypatch, provider) -> None:
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


async def create_tenant_with_key(client, session_factory, email: str) -> tuple[int, str]:
    headers = await register_and_login(client, email)
    owner_id = await user_id_for(client, headers)
    response = await client.post(
        "/api/v1/tenants", json={"name": email.split("@")[0]}, headers=headers
    )
    tenant_id = response.json()["id"]
    plaintext = security.generate_embed_key()
    async with session_factory() as session:
        session.add(
            ApiKey(
                tenant_id=tenant_id,
                name="Widget",
                prefix=security.embed_key_prefix(plaintext),
                key_hash=security.hash_token(plaintext),
                created_by=owner_id,
            )
        )
        await session.commit()
    return tenant_id, plaintext


async def open_session(client, embed_key: str) -> str:
    response = await client.post(
        "/api/v1/widget/session", headers={"X-Embed-Key": embed_key}
    )
    return response.json()["visitor_token"]


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


def widget_headers(embed_key: str, visitor_token: str) -> dict[str, str]:
    return {"X-Embed-Key": embed_key, "X-Visitor-Token": visitor_token}


async def test_widget_config_returns_tenant_info(client, session_factory):
    _, embed_key = await create_tenant_with_key(client, session_factory, "cfg@example.com")

    response = await client.get(
        "/api/v1/widget/config", headers={"X-Embed-Key": embed_key}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_name"] == "cfg"
    assert body["answer_mode"] == "strict"
    assert body["default_locale"]

    missing = await client.get("/api/v1/widget/config")
    assert missing.status_code == 401


async def test_widget_chat_persists_conversation_for_visitor(
    client, qdrant, session_factory, monkeypatch
):
    tenant_id, embed_key = await create_tenant_with_key(
        client, session_factory, "chatwidget@example.com"
    )
    await index_texts(qdrant, tenant_id, [CHUNK_TEXT])
    provider = FakeProvider()
    patch_provider(monkeypatch, provider)
    visitor_token = await open_session(client, embed_key)

    response = await client.post(
        "/api/v1/widget/chat",
        json={"message": QUERY},
        headers=widget_headers(embed_key, visitor_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Risposta widget"
    assert body["grounded"] is True
    assert body["conversation_id"] > 0
    assert len(body["sources"]) == 1

    async with session_factory() as session:
        conversation = (await session.exec(select(Conversation))).one()
        messages = (await session.exec(select(Message).order_by(Message.id))).all()
    assert conversation.user_id is None
    assert conversation.end_user_id is not None
    assert [m.role.value for m in messages] == ["user", "assistant"]


async def test_widget_chat_requires_visitor_token(client, qdrant, session_factory):
    _, embed_key = await create_tenant_with_key(
        client, session_factory, "notoken@example.com"
    )

    response = await client.post(
        "/api/v1/widget/chat",
        json={"message": "ciao"},
        headers={"X-Embed-Key": embed_key},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "VISITOR_TOKEN_REQUIRED"


async def test_widget_chat_rejects_foreign_visitor_token(
    client, qdrant, session_factory
):
    tenant_id, embed_key = await create_tenant_with_key(
        client, session_factory, "mismatch@example.com"
    )
    foreign = security.create_visitor_token(tenant_id + 999)

    response = await client.post(
        "/api/v1/widget/chat",
        json={"message": "ciao"},
        headers=widget_headers(embed_key, foreign),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "VISITOR_TENANT_MISMATCH"


async def test_widget_chat_stream_emits_events(
    client, qdrant, session_factory, monkeypatch
):
    tenant_id, embed_key = await create_tenant_with_key(
        client, session_factory, "streamwidget@example.com"
    )
    await index_texts(qdrant, tenant_id, [CHUNK_TEXT])
    provider = FakeProvider()
    patch_provider(monkeypatch, provider)
    visitor_token = await open_session(client, embed_key)

    response = await client.post(
        "/api/v1/widget/chat/stream",
        json={"message": QUERY},
        headers=widget_headers(embed_key, visitor_token),
    )

    assert response.status_code == 200
    events = parse_events(response.text)
    assert [name for name, _ in events] == ["sources", "token", "token", "done"]
    assert events[0][1]["conversation_id"] > 0
    assert events[-1][1]["provider"] == "ollama"

    async with session_factory() as session:
        messages = (await session.exec(select(Message).order_by(Message.id))).all()
    assert [m.role.value for m in messages] == ["user", "assistant"]


async def test_widget_chat_is_rate_limited(client, qdrant, session_factory, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("WIDGET_RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()

    async def deny(*args, **kwargs):
        return False

    monkeypatch.setattr("app.services.rate_limit.check_rate_limit", deny)

    tenant_id, embed_key = await create_tenant_with_key(
        client, session_factory, "limited@example.com"
    )
    visitor_token = security.create_visitor_token(tenant_id)

    response = await client.post(
        "/api/v1/widget/chat",
        json={"message": "ciao"},
        headers=widget_headers(embed_key, visitor_token),
    )
    streamed = await client.post(
        "/api/v1/widget/chat/stream",
        json={"message": "ciao"},
        headers=widget_headers(embed_key, visitor_token),
    )

    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"
    assert streamed.status_code == 429
    assert streamed.json()["code"] == "RATE_LIMITED"


async def test_widget_session_is_rate_limited(client, session_factory, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("WIDGET_RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()

    async def deny(*args, **kwargs):
        return False

    monkeypatch.setattr("app.services.rate_limit.check_rate_limit", deny)

    _, embed_key = await create_tenant_with_key(
        client, session_factory, "limited-session@example.com"
    )

    response = await client.post(
        "/api/v1/widget/session", headers={"X-Embed-Key": embed_key}
    )

    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"


async def test_widget_conversations_are_isolated_per_visitor(
    client, qdrant, session_factory, monkeypatch
):
    tenant_id, embed_key = await create_tenant_with_key(
        client, session_factory, "isolation@example.com"
    )
    await index_texts(qdrant, tenant_id, [CHUNK_TEXT])
    patch_provider(monkeypatch, FakeProvider())

    first_token = await open_session(client, embed_key)
    await client.post(
        "/api/v1/widget/chat",
        json={"message": QUERY},
        headers=widget_headers(embed_key, first_token),
    )
    async with session_factory() as session:
        conversation = (await session.exec(select(Conversation))).one()

    second_token = await open_session(client, embed_key)

    listed_second = await client.get(
        "/api/v1/widget/conversations",
        headers=widget_headers(embed_key, second_token),
    )
    detail_second = await client.get(
        f"/api/v1/widget/conversations/{conversation.id}",
        headers=widget_headers(embed_key, second_token),
    )
    listed_first = await client.get(
        "/api/v1/widget/conversations",
        headers=widget_headers(embed_key, first_token),
    )
    detail_first = await client.get(
        f"/api/v1/widget/conversations/{conversation.id}",
        headers=widget_headers(embed_key, first_token),
    )

    assert listed_second.status_code == 200
    assert listed_second.json() == []
    assert detail_second.status_code == 404
    assert len(listed_first.json()) == 1
    assert detail_first.status_code == 200
    assert [m["role"] for m in detail_first.json()["messages"]] == [
        "user",
        "assistant",
    ]


async def test_widget_conversations_are_paginated(
    client, qdrant, session_factory, monkeypatch
):
    tenant_id, embed_key = await create_tenant_with_key(
        client, session_factory, "paged@example.com"
    )
    await index_texts(qdrant, tenant_id, [CHUNK_TEXT])
    patch_provider(monkeypatch, FakeProvider())
    visitor_token = await open_session(client, embed_key)
    headers = widget_headers(embed_key, visitor_token)

    for index in range(5):
        response = await client.post(
            "/api/v1/widget/chat",
            json={"message": f"domanda {index}"},
            headers=headers,
        )
        assert response.status_code == 200

    full = await client.get("/api/v1/widget/conversations", headers=headers)
    assert len(full.json()) == 5

    page = await client.get(
        "/api/v1/widget/conversations?limit=2&offset=1", headers=headers
    )
    assert [item["id"] for item in page.json()] == [
        item["id"] for item in full.json()[1:3]
    ]


async def test_widget_read_routes_are_rate_limited(client, session_factory, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("WIDGET_RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()

    async def deny(*args, **kwargs):
        return False

    monkeypatch.setattr("app.services.rate_limit.check_rate_limit", deny)

    tenant_id, embed_key = await create_tenant_with_key(
        client, session_factory, "limited-read@example.com"
    )
    visitor_token = security.create_visitor_token(tenant_id)
    headers = widget_headers(embed_key, visitor_token)

    config = await client.get("/api/v1/widget/config", headers=headers)
    listed = await client.get("/api/v1/widget/conversations", headers=headers)
    fetched = await client.get(
        "/api/v1/widget/conversations/1", headers=headers
    )

    assert config.status_code == 429
    assert config.json()["code"] == "RATE_LIMITED"
    assert listed.status_code == 429
    assert fetched.status_code == 429


async def test_widget_chat_honours_request_locale(
    client, qdrant, session_factory, monkeypatch
):
    _, embed_key = await create_tenant_with_key(
        client, session_factory, "localewidget@example.com"
    )
    patch_provider(monkeypatch, FakeProvider())
    visitor_token = await open_session(client, embed_key)
    headers = widget_headers(embed_key, visitor_token)

    english = await client.post(
        "/api/v1/widget/chat",
        json={"message": QUERY, "locale": "en"},
        headers=headers,
    )
    default = await client.post(
        "/api/v1/widget/chat",
        json={"message": QUERY},
        headers=headers,
    )

    assert english.status_code == 200
    assert english.json()["grounded"] is False
    assert english.json()["answer"] == (
        "I could not find this information in the available documents."
    )
    assert default.json()["answer"] == (
        "Non ho trovato questa informazione nei documenti disponibili."
    )


async def test_widget_chat_stream_honours_request_locale(
    client, qdrant, session_factory, monkeypatch
):
    _, embed_key = await create_tenant_with_key(
        client, session_factory, "localestream@example.com"
    )
    patch_provider(monkeypatch, FakeProvider())
    visitor_token = await open_session(client, embed_key)

    response = await client.post(
        "/api/v1/widget/chat/stream",
        json={"message": QUERY, "locale": "en"},
        headers=widget_headers(embed_key, visitor_token),
    )

    assert response.status_code == 200
    events = parse_events(response.text)
    assert [name for name, _ in events] == ["sources", "token", "done"]
    assert events[1][1]["text"] == (
        "I could not find this information in the available documents."
    )


async def test_widget_chat_rejects_unsupported_locale(
    client, qdrant, session_factory
):
    _, embed_key = await create_tenant_with_key(
        client, session_factory, "badlocale@example.com"
    )
    visitor_token = await open_session(client, embed_key)

    response = await client.post(
        "/api/v1/widget/chat",
        json={"message": "ciao", "locale": "fr"},
        headers=widget_headers(embed_key, visitor_token),
    )

    assert response.status_code == 422
