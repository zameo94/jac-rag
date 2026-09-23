import json

import pytest
from qdrant_client import AsyncQdrantClient
from sqlmodel import select

from app.api.v1 import chat as chat_module
from app.main import app
from app.models import Conversation, Message, Setting
from app.schemas.setting import SettingScope
from app.services.llm import LLMProvider, LLMProviderError, LLMResponse
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


class StreamingProvider(LLMProvider):
    name = "ollama"

    def __init__(
        self,
        pieces=("Ciao", " mondo"),
        fail_after: int | None = None,
        internal_fail_after: int | None = None,
    ) -> None:
        self.pieces = pieces
        self.fail_after = fail_after
        self.internal_fail_after = internal_fail_after
        self.calls: list[list] = []
        self.closed = False

    async def generate(self, messages, *, model=None, temperature=0.0):
        return LLMResponse(content="".join(self.pieces), model=model or "m", provider=self.name)

    async def stream(self, messages, *, model=None, temperature=0.0):
        self.calls.append(list(messages))
        for index, piece in enumerate(self.pieces):
            if self.fail_after is not None and index >= self.fail_after:
                raise LLMProviderError("LLM_UNAVAILABLE", "boom")
            if self.internal_fail_after is not None and index >= self.internal_fail_after:
                raise RuntimeError("internal boom")
            yield piece

    async def aclose(self) -> None:
        self.closed = True


def patch_provider(monkeypatch, provider) -> None:
    async def build(session, workspace_id, provider_id, model=None):
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


async def create_workspace(client, headers, name: str = "Acme") -> int:
    response = await client.post("/api/v1/workspaces", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def index_texts(qdrant, workspace_id: int, texts) -> None:
    vectors = await embeddings.embed_texts(texts)
    await vector_store.upsert_chunks(
        qdrant,
        workspace_id,
        1,
        "doc.md",
        [(index, text) for index, text in enumerate(texts)],
        vectors,
    )


async def test_stream_emits_sources_tokens_and_done(
    client, qdrant, session_factory, monkeypatch
):
    headers = await register_and_login(client, "stream-owner@example.com")
    workspace_id = await create_workspace(client, headers)
    await index_texts(qdrant, workspace_id, [CHUNK_TEXT])
    provider = StreamingProvider()
    patch_provider(monkeypatch, provider)

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/chat/stream",
        json={"message": QUERY},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_events(response.text)
    assert [name for name, _ in events] == ["sources", "token", "token", "done"]
    assert events[0][1]["grounded"] is True
    assert events[0][1]["conversation_id"] is not None
    assert len(events[0][1]["sources"]) == 1
    assert "".join(data["text"] for name, data in events if name == "token") == "Ciao mondo"
    assert events[-1][1]["provider"] == "ollama"
    assert provider.closed is True

    async with session_factory() as session:
        messages = (await session.exec(select(Message).order_by(Message.id))).all()
    assert [m.role.value for m in messages] == ["user", "assistant"]
    assert messages[1].sources


async def test_stream_strict_refusal_without_context(
    client, qdrant, session_factory, monkeypatch
):
    headers = await register_and_login(client, "stream-refusal@example.com")
    workspace_id = await create_workspace(client, headers)
    provider = StreamingProvider()
    patch_provider(monkeypatch, provider)

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/chat/stream",
        json={"message": "Domanda senza contesto"},
        headers=headers,
    )

    events = parse_events(response.text)
    assert [name for name, _ in events] == ["sources", "token", "done"]
    assert events[0][1]["grounded"] is False
    assert events[0][1]["sources"] == []
    assert events[0][1]["conversation_id"] is not None
    assert provider.calls == []
    assert provider.closed is True


async def test_stream_provider_error_mid_stream(
    client, qdrant, session_factory, monkeypatch
):
    headers = await register_and_login(client, "stream-error@example.com")
    workspace_id = await create_workspace(client, headers)
    await index_texts(qdrant, workspace_id, [CHUNK_TEXT])
    provider = StreamingProvider(pieces=("A", "B"), fail_after=1)
    patch_provider(monkeypatch, provider)

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/chat/stream",
        json={"message": QUERY},
        headers=headers,
    )

    assert response.status_code == 200
    events = parse_events(response.text)
    assert [name for name, _ in events] == ["sources", "token", "error"]
    assert events[-1][1]["code"] == "LLM_UNAVAILABLE"
    assert provider.closed is True

    async with session_factory() as session:
        messages = (await session.exec(select(Message).order_by(Message.id))).all()
    assert messages[-1].error_code == "LLM_UNAVAILABLE"
    assert messages[-1].content == "A"


async def test_stream_internal_error_mid_stream(
    client, qdrant, session_factory, monkeypatch
):
    headers = await register_and_login(client, "stream-internal@example.com")
    workspace_id = await create_workspace(client, headers)
    await index_texts(qdrant, workspace_id, [CHUNK_TEXT])
    provider = StreamingProvider(pieces=("A", "B"), internal_fail_after=1)
    patch_provider(monkeypatch, provider)

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/chat/stream",
        json={"message": QUERY},
        headers=headers,
    )

    assert response.status_code == 200
    events = parse_events(response.text)
    assert [name for name, _ in events] == ["sources", "token", "error"]
    assert events[-1][1]["code"] == "STREAM_INTERNAL_ERROR"
    assert provider.closed is True

    async with session_factory() as session:
        messages = (await session.exec(select(Message).order_by(Message.id))).all()
    assert messages[-1].error_code == "STREAM_INTERNAL_ERROR"
    assert messages[-1].content == "A"


async def test_stream_internal_error_before_first_token_hides_details(
    client, qdrant, session_factory, monkeypatch
):
    headers = await register_and_login(client, "stream-internal-early@example.com")
    workspace_id = await create_workspace(client, headers)
    await index_texts(qdrant, workspace_id, [CHUNK_TEXT])
    provider = StreamingProvider(pieces=("A",), internal_fail_after=0)
    patch_provider(monkeypatch, provider)

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/chat/stream",
        json={"message": QUERY},
        headers=headers,
    )

    events = parse_events(response.text)
    assert [name for name, _ in events] == ["sources", "error"]

    async with session_factory() as session:
        messages = (await session.exec(select(Message).order_by(Message.id))).all()
    assert messages[-1].error_code == "STREAM_INTERNAL_ERROR"
    assert messages[-1].content == "Unexpected error"


async def test_stream_rejects_disabled_provider_before_stream(
    client, qdrant, session_factory
):
    headers = await register_and_login(client, "stream-disabled@example.com")
    workspace_id = await create_workspace(client, headers)
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
        f"/api/v1/workspaces/{workspace_id}/chat/stream",
        json={"message": "ciao"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "PROVIDER_NOT_AVAILABLE"


async def test_stream_requires_authentication(client, qdrant):
    response = await client.post(
        "/api/v1/workspaces/1/chat/stream", json={"message": "ciao"}
    )

    assert response.status_code == 401


async def test_stream_rejects_non_member(client, qdrant):
    owner_headers = await register_and_login(client, "stream-a@example.com")
    workspace_id = await create_workspace(client, owner_headers)
    other_headers = await register_and_login(client, "stream-b@example.com")

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/chat/stream",
        json={"message": "ciao"},
        headers=other_headers,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "NOT_A_MEMBER"


async def test_stream_reuses_conversation_with_history(
    client, qdrant, session_factory, monkeypatch
):
    headers = await register_and_login(client, "stream-history@example.com")
    workspace_id = await create_workspace(client, headers)
    await index_texts(qdrant, workspace_id, [CHUNK_TEXT])
    provider = StreamingProvider()
    patch_provider(monkeypatch, provider)

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/chat/stream",
        json={"message": QUERY},
        headers=headers,
    )
    async with session_factory() as session:
        conversation_id = (await session.exec(select(Conversation))).one().id

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/chat/stream",
        json={"message": QUERY, "conversation_id": conversation_id},
        headers=headers,
    )

    assert [m.role.value for m in provider.calls[1]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]


async def test_stream_disconnect_persists_partial_reply(
    client, qdrant, session_factory, monkeypatch
):
    import asyncio

    from app.schemas.workspace import AnswerMode
    from app.services.rag.chat.execute import stream_events
    from app.services.rag.chat.prepare import PreparedChat

    headers = await register_and_login(client, "stream-conn@example.com")
    workspace_id = await create_workspace(client, headers)
    user_id = await user_id_for(client, headers)
    async with session_factory() as session:
        conversation = Conversation(
            workspace_id=workspace_id, user_id=user_id, title="test"
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)

    provider = StreamingProvider(pieces=("A", "B"))
    patch_provider(monkeypatch, provider)
    prepared = PreparedChat(
        provider=provider,
        provider_id="ollama",
        model="m",
        grounded=True,
        used_chunks=[],
        conversation=conversation,
        history=[],
        answer_mode=AnswerMode.ASSISTIVE,
        locale="it",
    )

    generator = stream_events(prepared, "ciao")
    await generator.__anext__()
    await generator.__anext__()
    with pytest.raises(asyncio.CancelledError):
        await generator.athrow(asyncio.CancelledError())

    assert provider.closed is True

    async def wait_for_message() -> Message:
        async with asyncio.timeout(5):
            while True:
                async with session_factory() as session:
                    message = (
                        await session.exec(select(Message).order_by(Message.id))
                    ).all()
                if message:
                    return message[0]
                await asyncio.sleep(0.02)

    saved = await wait_for_message()
    assert saved.role.value == "assistant"
    assert saved.content == "A"
    assert saved.error_code == "CLIENT_DISCONNECTED"
    assert saved.grounded is False
