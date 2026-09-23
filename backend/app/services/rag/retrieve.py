from __future__ import annotations

from qdrant_client import AsyncQdrantClient

from app.core.config import get_settings
from app.services.rag import bm25, embeddings, vector_store
from app.services.rag.vector_store import RetrievedChunk


async def retrieve_chunks(
    client: AsyncQdrantClient,
    workspace_id: int,
    query: str,
    *,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    settings = get_settings()
    limit = top_k or settings.retrieval_top_k
    vector = await embeddings.embed_query(query)
    dense = await vector_store.search_chunks(client, workspace_id, vector, limit)
    if not settings.hybrid_enabled:
        return dense

    index = await bm25.get_lexical_index(client, workspace_id)
    lexical = bm25.search_index(index, query, limit) if index is not None else []
    return bm25.reciprocal_rank_fusion(dense, lexical, limit=limit, k=settings.rrf_k)


def has_context(chunks: list[RetrievedChunk]) -> bool:
    """Deterministic relevance gate on the best dense score. No LLM router.

    The dense score stays authoritative even when hybrid search reorders the
    candidates, so the calibrated threshold keeps its meaning.
    """
    return bool(chunks) and max(chunk.score for chunk in chunks) >= get_settings().relevance_threshold
