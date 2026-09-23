import pytest
from qdrant_client import AsyncQdrantClient

from app.api.v1 import chat as chat_module
from app.core.config import get_settings
from app.main import app
from app.services.llm import LLMProvider, LLMResponse
from app.services.rag import embeddings, vector_store
from app.services.rag import rerank as rerank_module
from app.services.rag.vector_store import RetrievedChunk
from tests.helpers import register_and_login

CHUNK_TEXT = "Il colore preferito della macchina aziendale e il blu."
QUERY = "Qual e il colore preferito della macchina aziendale?"


def chunk(text: str, score: float = 0.5, index: int = 0) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=1, chunk_index=index, text=text, score=score, filename="doc.md"
    )


class FakeReranker:
    def rerank(self, query: str, documents, batch_size: int = 64):
        return [float(len(document)) for document in documents]


class FakeProvider(LLMProvider):
    name = "ollama"

    def __init__(self) -> None:
        self.calls: list[list] = []

    async def generate(self, messages, *, model=None, temperature=0.0):
        self.calls.append(list(messages))
        return LLMResponse(content="ok", model=model or "llama3.2", provider=self.name)

    async def stream(self, messages, *, model=None, temperature=0.0):
        yield "ok"


class OrderedProvider(FakeProvider):
    def __init__(self, order: list[str]) -> None:
        super().__init__()
        self.order = order

    async def generate(self, messages, *, model=None, temperature=0.0):
        self.order.append("generate")
        return await super().generate(messages, model=model, temperature=temperature)


async def fake_rerank(query, chunks, *, top_k):
    return chunks[:1]


async def rerank_reorder(order: list[str], chunks):
    order.append("rerank")
    return chunks[:1]


async def test_rerank_orders_by_cross_encoder(monkeypatch):
    monkeypatch.setattr(rerank_module, "get_reranker", lambda: FakeReranker())
    chunks = [chunk("short"), chunk("a much longer passage than the other")]

    result = await rerank_module.rerank_chunks("q", chunks, top_k=1)

    assert result[0].text == "a much longer passage than the other"


async def test_rerank_passes_configured_batch_size(monkeypatch):
    monkeypatch.setenv("RERANK_BATCH_SIZE", "7")
    get_settings.cache_clear()
    seen: dict[str, int] = {}

    class RecordingReranker:
        def rerank(self, query, documents, batch_size=64):
            seen["batch_size"] = batch_size
            return [0.0 for _ in documents]

    monkeypatch.setattr(rerank_module, "get_reranker", lambda: RecordingReranker())

    await rerank_module.rerank_chunks("q", [chunk("a")], top_k=1)

    assert seen["batch_size"] == 7


async def test_rerank_empty_returns_empty(monkeypatch):
    monkeypatch.setattr(rerank_module, "get_reranker", lambda: FakeReranker())

    assert await rerank_module.rerank_chunks("q", [], top_k=5) == []


async def test_rerank_non_positive_top_k(monkeypatch):
    monkeypatch.setattr(rerank_module, "get_reranker", lambda: FakeReranker())

    assert await rerank_module.rerank_chunks("q", [chunk("a")], top_k=0) == []


def test_preload_reranker_skips_when_disabled(monkeypatch):
    from app import main as main_module

    calls: list[int] = []
    monkeypatch.setattr(main_module.rerank, "get_reranker", lambda: calls.append(1))

    main_module.preload_reranker()

    assert calls == []


def test_preload_reranker_loads_when_warmup(monkeypatch):
    from app import main as main_module

    monkeypatch.setenv("RERANK_ENABLED", "true")
    monkeypatch.setenv("RERANK_MODE", "warmup")
    get_settings.cache_clear()
    calls: list[int] = []
    monkeypatch.setattr(main_module.rerank, "get_reranker", lambda: calls.append(1))

    main_module.preload_reranker()

    assert calls == [1]


def test_preload_reranker_skips_when_on_demand(monkeypatch):
    from app import main as main_module

    monkeypatch.setenv("RERANK_ENABLED", "true")
    monkeypatch.setenv("RERANK_MODE", "on_demand")
    get_settings.cache_clear()
    calls: list[int] = []
    monkeypatch.setattr(main_module.rerank, "get_reranker", lambda: calls.append(1))

    main_module.preload_reranker()

    assert calls == []


@pytest.fixture(autouse=True)
def _reset_reranker():
    rerank_module.release_reranker()
    yield
    rerank_module.release_reranker()


def test_release_reranker_frees_and_reloads(monkeypatch):
    loads: list[int] = []

    def load():
        loads.append(1)
        return FakeReranker()

    monkeypatch.setattr(rerank_module, "_load_reranker", load)

    first = rerank_module.get_reranker()
    assert rerank_module.get_reranker() is first

    rerank_module.release_reranker()

    second = rerank_module.get_reranker()
    assert second is not first
    assert len(loads) == 2


def test_release_reranker_without_instance(monkeypatch):
    monkeypatch.setattr(rerank_module, "_load_reranker", lambda: FakeReranker())
    rerank_module.release_reranker()

    assert rerank_module._reranker is None


@pytest.fixture
async def qdrant():
    client = AsyncQdrantClient(":memory:")

    async def override():
        yield client

    app.dependency_overrides[chat_module.get_vector_client] = override
    yield client
    await client.close()
    app.dependency_overrides.pop(chat_module.get_vector_client, None)


async def create_workspace(client, headers) -> int:
    response = await client.post("/api/v1/workspaces", json={"name": "Acme"}, headers=headers)
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


async def test_chat_uses_reranked_context(client, qdrant, monkeypatch):
    monkeypatch.setenv("RERANK_ENABLED", "true")
    get_settings.cache_clear()
    headers = await register_and_login(client, "rerank-owner@example.com")
    workspace_id = await create_workspace(client, headers)
    await index_texts(qdrant, workspace_id, [CHUNK_TEXT, "contenuto diverso senza risposta"])

    fake = FakeProvider()

    async def build(session, workspace_id, provider_id, model=None):
        return fake, "llama3.2"

    monkeypatch.setattr("app.services.rag.chat.prepare.build_provider", build)
    monkeypatch.setattr(
        "app.services.rag.chat.prepare.rerank_chunks",
        fake_rerank,
    )

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/chat",
        json={"message": QUERY},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["sources"]) == 1


async def test_chat_releases_reranker_before_generation(client, qdrant, monkeypatch):
    monkeypatch.setenv("RERANK_ENABLED", "true")
    monkeypatch.setenv("RERANK_MODE", "on_demand")
    get_settings.cache_clear()
    headers = await register_and_login(client, "release-owner@example.com")
    workspace_id = await create_workspace(client, headers)
    await index_texts(qdrant, workspace_id, [CHUNK_TEXT, "contenuto diverso senza risposta"])

    order: list[str] = []

    async def build(session, workspace_id, provider_id, model=None):
        return OrderedProvider(order), "llama3.2"

    monkeypatch.setattr("app.services.rag.chat.prepare.build_provider", build)
    monkeypatch.setattr(
        "app.services.rag.chat.prepare.rerank_chunks",
        lambda query, chunks, *, top_k: rerank_reorder(order, chunks),
    )
    monkeypatch.setattr(
        "app.services.rag.chat.prepare.release_reranker",
        lambda: order.append("release"),
    )

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/chat",
        json={"message": QUERY},
        headers=headers,
    )

    assert response.status_code == 200
    assert order == ["rerank", "release", "generate"]


async def test_chat_keeps_reranker_when_warmup(client, qdrant, monkeypatch):
    monkeypatch.setenv("RERANK_ENABLED", "true")
    monkeypatch.setenv("RERANK_MODE", "warmup")
    get_settings.cache_clear()
    headers = await register_and_login(client, "warmup-owner@example.com")
    workspace_id = await create_workspace(client, headers)
    await index_texts(qdrant, workspace_id, [CHUNK_TEXT, "contenuto diverso senza risposta"])

    order: list[str] = []

    async def build(session, workspace_id, provider_id, model=None):
        return OrderedProvider(order), "llama3.2"

    monkeypatch.setattr("app.services.rag.chat.prepare.build_provider", build)
    monkeypatch.setattr(
        "app.services.rag.chat.prepare.rerank_chunks",
        lambda query, chunks, *, top_k: rerank_reorder(order, chunks),
    )
    monkeypatch.setattr(
        "app.services.rag.chat.prepare.release_reranker",
        lambda: order.append("release"),
    )

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/chat",
        json={"message": QUERY},
        headers=headers,
    )

    assert response.status_code == 200
    assert order == ["rerank", "generate"]


async def test_chat_context_is_capped_by_chat_context_k(client, qdrant, monkeypatch):
    monkeypatch.setenv("RETRIEVAL_TOP_K", "5")
    monkeypatch.setenv("CHAT_CONTEXT_K", "2")
    get_settings.cache_clear()
    headers = await register_and_login(client, "cap-owner@example.com")
    workspace_id = await create_workspace(client, headers)
    await index_texts(qdrant, workspace_id, [f"{CHUNK_TEXT} {i}" for i in range(5)])

    fake = FakeProvider()

    async def build(session, workspace_id, provider_id, model=None):
        return fake, "llama3.2"

    monkeypatch.setattr("app.services.rag.chat.prepare.build_provider", build)

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/chat",
        json={"message": QUERY},
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()["sources"]) == 2
