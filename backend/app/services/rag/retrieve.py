from __future__ import annotations

from qdrant_client import AsyncQdrantClient

from app.core.config import get_settings
from app.services.rag import embeddings, vector_store
from app.services.rag.vector_store import RetrievedChunk


async def retrieve_chunks(
    client: AsyncQdrantClient,
    tenant_id: int,
    query: str,
    *,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    settings = get_settings()
    vector = embeddings.embed_query(query)
    return await vector_store.search_chunks(
        client, tenant_id, vector, top_k or settings.retrieval_top_k
    )


def has_context(chunks: list[RetrievedChunk]) -> bool:
    """Deterministic relevance gate on the best dense score. No LLM router."""
    return bool(chunks) and chunks[0].score >= get_settings().relevance_threshold
