from __future__ import annotations

import asyncio
import gc

from app.core.config import get_settings
from app.services.rag.vector_store import RetrievedChunk

_rerank_semaphore = asyncio.Semaphore(2)

_reranker = None


def _load_reranker():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=get_settings().rerank_model)


def get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = _load_reranker()
    return _reranker


def release_reranker() -> None:
    """Drop the resident cross-encoder so its memory is freed for the LLM."""
    global _reranker
    if _reranker is None:
        return
    _reranker = None
    gc.collect()


def _rerank_chunks_sync(
    query: str, chunks: list[RetrievedChunk], top_k: int
) -> list[RetrievedChunk]:
    """Reorder candidates with a cross-encoder and keep the best ``top_k``.

    The reranker only reorders; the retrieved chunks keep their dense score so
    the relevance gate stays anchored to the dense similarity.
    """
    reranker = get_reranker()
    scores = list(
        reranker.rerank(
            query,
            [chunk.text for chunk in chunks],
            batch_size=get_settings().rerank_batch_size,
        )
    )
    ranked = sorted(zip(chunks, scores), key=lambda pair: pair[1], reverse=True)
    return [chunk for chunk, _ in ranked[:top_k]]


async def rerank_chunks(
    query: str, chunks: list[RetrievedChunk], *, top_k: int
) -> list[RetrievedChunk]:
    """Async wrapper; the cross-encoder runs in a worker thread."""
    if top_k <= 0 or not chunks:
        return []
    async with _rerank_semaphore:
        return await asyncio.to_thread(_rerank_chunks_sync, query, chunks, top_k)
