from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import get_settings


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: int
    chunk_index: int
    text: str
    score: float
    filename: str


def collection_name(tenant_id: int) -> str:
    return f"tenant_{tenant_id}"


def get_qdrant_client() -> AsyncQdrantClient:
    settings = get_settings()
    if settings.qdrant_url == ":memory:":
        return AsyncQdrantClient(":memory:")
    return AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


async def ensure_collection(client: AsyncQdrantClient, tenant_id: int) -> None:
    name = collection_name(tenant_id)
    if await client.collection_exists(name):
        return
    await client.create_collection(
        name,
        vectors_config=VectorParams(
            size=get_settings().embedding_dim,
            distance=Distance.COSINE,
        ),
    )


async def delete_collection(client: AsyncQdrantClient, tenant_id: int) -> None:
    name = collection_name(tenant_id)
    if await client.collection_exists(name):
        await client.delete_collection(name)


async def upsert_chunks(
    client: AsyncQdrantClient,
    tenant_id: int,
    document_id: int,
    filename: str,
    chunks: list[tuple[int, str]],
    vectors: list[list[float]],
    metadatas: list[dict] | None = None,
) -> int:
    await ensure_collection(client, tenant_id)
    points = []
    for position, ((index, text), vector) in enumerate(zip(chunks, vectors)):
        payload: dict = {
            "document_id": document_id,
            "chunk_index": index,
            "text": text,
            "filename": filename,
        }
        if metadatas is not None and position < len(metadatas):
            payload.update(metadatas[position])
        points.append(
            PointStruct(id=_point_id(document_id, index), vector=vector, payload=payload)
        )
    if points:
        await client.upsert(collection_name(tenant_id), points=points)
    return len(points)


async def delete_document_chunks(
    client: AsyncQdrantClient, tenant_id: int, document_id: int
) -> None:
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    name = collection_name(tenant_id)
    if not await client.collection_exists(name):
        return
    await client.delete(
        name,
        points_selector=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        ),
    )


async def search_chunks(
    client: AsyncQdrantClient,
    tenant_id: int,
    query_vector: list[float],
    limit: int,
) -> list[RetrievedChunk]:
    name = collection_name(tenant_id)
    if not await client.collection_exists(name):
        return []
    response = await client.query_points(name, query=query_vector, limit=limit)
    results = []
    for point in response.points:
        payload = point.payload or {}
        results.append(
            RetrievedChunk(
                document_id=payload.get("document_id", 0),
                chunk_index=payload.get("chunk_index", 0),
                text=payload.get("text", ""),
                score=point.score,
                filename=payload.get("filename", ""),
            )
        )
    return results


def _point_id(document_id: int, chunk_index: int) -> int:
    return document_id * 1_000_000 + chunk_index
