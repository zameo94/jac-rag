import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance

from app.core.config import get_settings
from app.services.rag import vector_store


def unit_vector(position: int) -> list[float]:
    vector = [0.0] * get_settings().embedding_dim
    vector[position] = 1.0
    return vector


@pytest.fixture
async def qdrant():
    client = AsyncQdrantClient(":memory:")
    yield client
    await client.close()


def test_collection_name_is_tenant_scoped():
    assert vector_store.collection_name(5) == "tenant_5"
    assert vector_store.collection_name(1) != vector_store.collection_name(2)


async def test_ensure_collection_creates_collection(qdrant):
    await vector_store.ensure_collection(qdrant, 1)

    assert await qdrant.collection_exists("tenant_1")


async def test_ensure_collection_is_idempotent(qdrant):
    await vector_store.ensure_collection(qdrant, 1)
    await vector_store.ensure_collection(qdrant, 1)

    assert await qdrant.collection_exists("tenant_1")


async def test_ensure_collection_uses_configured_dimension(qdrant):
    await vector_store.ensure_collection(qdrant, 2)

    info = await qdrant.get_collection("tenant_2")
    assert info.config.params.vectors.size == get_settings().embedding_dim
    assert info.config.params.vectors.distance == Distance.COSINE


async def test_delete_collection_removes_collection(qdrant):
    await vector_store.ensure_collection(qdrant, 3)

    await vector_store.delete_collection(qdrant, 3)

    assert not await qdrant.collection_exists("tenant_3")


async def test_delete_collection_is_idempotent(qdrant):
    await vector_store.delete_collection(qdrant, 404)


async def test_upsert_chunks_stores_points(qdrant):
    vectors = [unit_vector(0), unit_vector(1)]

    count = await vector_store.upsert_chunks(
        qdrant, 1, 10, "doc.txt", [(0, "primo"), (1, "secondo")], vectors
    )

    assert count == 2
    info = await qdrant.get_collection("tenant_1")
    assert info.points_count == 2


async def test_upsert_chunks_returns_zero_for_empty(qdrant):
    count = await vector_store.upsert_chunks(qdrant, 1, 10, "doc.txt", [], [])

    assert count == 0


async def test_search_chunks_returns_ordered_results(qdrant):
    await vector_store.upsert_chunks(
        qdrant, 1, 10, "doc.txt", [(0, "alpha"), (1, "beta")], [unit_vector(0), unit_vector(1)]
    )

    results = await vector_store.search_chunks(qdrant, 1, unit_vector(0), limit=2)

    assert results[0].text == "alpha"
    assert results[0].score > results[1].score
    assert results[0].document_id == 10
    assert results[0].filename == "doc.txt"


async def test_search_chunks_on_missing_collection_returns_empty(qdrant):
    results = await vector_store.search_chunks(qdrant, 999, unit_vector(0), limit=5)

    assert results == []


async def test_delete_document_chunks_removes_only_target_document(qdrant):
    await vector_store.upsert_chunks(qdrant, 1, 10, "a.txt", [(0, "a")], [unit_vector(0)])
    await vector_store.upsert_chunks(qdrant, 1, 11, "b.txt", [(0, "b")], [unit_vector(1)])

    await vector_store.delete_document_chunks(qdrant, 1, 10)

    results = await vector_store.search_chunks(qdrant, 1, unit_vector(1), limit=10)
    assert len(results) == 1
    assert results[0].document_id == 11


async def test_delete_document_chunks_on_missing_collection(qdrant):
    await vector_store.delete_document_chunks(qdrant, 999, 1)


async def test_tenants_are_isolated_in_separate_collections(qdrant):
    await vector_store.upsert_chunks(qdrant, 1, 10, "a.txt", [(0, "tenant one")], [unit_vector(0)])
    await vector_store.upsert_chunks(qdrant, 2, 20, "b.txt", [(0, "tenant two")], [unit_vector(0)])

    results_one = await vector_store.search_chunks(qdrant, 1, unit_vector(0), limit=10)
    results_two = await vector_store.search_chunks(qdrant, 2, unit_vector(0), limit=10)

    assert [result.text for result in results_one] == ["tenant one"]
    assert [result.text for result in results_two] == ["tenant two"]


async def test_point_id_is_deterministic():
    assert vector_store._point_id(10, 3) == 10_000_003
    assert vector_store._point_id(10, 3) != vector_store._point_id(10, 4)
