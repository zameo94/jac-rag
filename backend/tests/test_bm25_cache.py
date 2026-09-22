import pytest
from qdrant_client import AsyncQdrantClient

from app.core.config import get_settings
from app.services.rag import bm25, vector_store


@pytest.fixture(autouse=True)
def _clear_cache():
    bm25._cache.clear()
    yield
    bm25._cache.clear()


def _zero_vector() -> list[float]:
    return [0.0] * get_settings().embedding_dim


async def upsert_document(client, tenant_id, document_id, texts) -> None:
    await vector_store.upsert_chunks(
        client,
        tenant_id,
        document_id,
        f"doc{document_id}.md",
        [(index, text) for index, text in enumerate(texts)],
        [_zero_vector() for _ in texts],
    )


async def test_get_lexical_index_missing_collection_returns_none():
    client = AsyncQdrantClient(":memory:")

    assert await bm25.get_lexical_index(client, 99) is None
    await client.close()


async def test_get_lexical_index_caches_and_reuses():
    client = AsyncQdrantClient(":memory:")
    await vector_store.ensure_collection(client, 1)
    await upsert_document(client, 1, 7, ["testo di prova"])

    first = await bm25.get_lexical_index(client, 1)
    second = await bm25.get_lexical_index(client, 1)

    assert first is second
    assert first.points_count == 1
    assert len(first.corpus) == 1
    await client.close()


async def test_get_lexical_index_rebuilds_when_point_count_changes(monkeypatch):
    monkeypatch.setattr(bm25, "CACHE_REVALIDATE_SECONDS", 0)
    client = AsyncQdrantClient(":memory:")
    await vector_store.ensure_collection(client, 1)
    await upsert_document(client, 1, 7, ["primo documento"])

    first = await bm25.get_lexical_index(client, 1)

    await upsert_document(client, 1, 8, ["secondo documento"])
    second = await bm25.get_lexical_index(client, 1)

    assert second is not first
    assert second.points_count == 2
    assert len(second.corpus) == 2
    await client.close()


async def test_get_lexical_index_skips_count_within_ttl(monkeypatch):
    client = AsyncQdrantClient(":memory:")
    await vector_store.ensure_collection(client, 1)
    await upsert_document(client, 1, 7, ["testo di prova"])

    calls = {"count": 0}
    original = client.count

    async def counting(*args, **kwargs):
        calls["count"] += 1
        return await original(*args, **kwargs)

    monkeypatch.setattr(client, "count", counting)

    first = await bm25.get_lexical_index(client, 1)
    second = await bm25.get_lexical_index(client, 1)

    assert first is second
    assert calls["count"] == 1
    await client.close()


async def test_get_lexical_index_rebuilds_same_count_after_invalidate():
    client = AsyncQdrantClient(":memory:")
    await vector_store.ensure_collection(client, 1)
    await upsert_document(client, 1, 7, ["documento A"])

    first = await bm25.get_lexical_index(client, 1)
    bm25.invalidate(1)

    second = await bm25.get_lexical_index(client, 1)

    assert second is not first
    assert second.points_count == 1
    await client.close()


async def test_get_lexical_index_evicts_least_recently_used(monkeypatch):
    monkeypatch.setattr(bm25, "MAX_CACHED_TENANTS", 2)
    client = AsyncQdrantClient(":memory:")
    for tenant_id in (1, 2, 3):
        await vector_store.ensure_collection(client, tenant_id)
        await upsert_document(client, tenant_id, 1, [f"testo del tenant {tenant_id}"])

    one = await bm25.get_lexical_index(client, 1)
    await bm25.get_lexical_index(client, 2)
    three = await bm25.get_lexical_index(client, 3)

    assert set(bm25._cache) == {2, 3}

    evicted = await bm25.get_lexical_index(client, 1)
    assert evicted is not one
    await client.close()


async def test_search_index_matches_search_ranking():
    client = AsyncQdrantClient(":memory:")
    await vector_store.ensure_collection(client, 1)
    texts = [
        "Il netto in busta del cedolino marzo 22 e 1.700,00",
        "Il netto in busta del cedolino febbraio 22 e 1.821,00",
        "Lettera di aumento retributivo del 2021",
    ]
    await upsert_document(client, 1, 1, texts)

    index = await bm25.get_lexical_index(client, 1)
    query = "quanto e il netto in busta febbraio 22"

    cached = bm25.search_index(index, query, 3)
    reference = bm25.search(
        [bm25.CorpusChunk(1, i, text, "doc1.md") for i, text in enumerate(texts)],
        query,
        3,
    )

    assert [(c.filename, round(score, 6)) for c, score in cached] == [
        (c.filename, round(score, 6)) for c, score in reference
    ]
    assert cached[0][0].text == texts[1]
    await client.close()