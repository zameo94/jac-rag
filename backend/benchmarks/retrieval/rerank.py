"""Benchmark adapter: wrap a retrieval index with a cross-encoder reranker.

Kept benchmark-only (never imported by the application). It over-fetches a
candidate window and reorders with fastembed's ``TextCrossEncoder``, mirroring
the production reranking step while recording per-query latency.
"""

from __future__ import annotations

import time
from dataclasses import replace

from fastembed.rerank.cross_encoder import TextCrossEncoder

from benchmarks.retrieval.runner import Hit


class RerankedIndex:
    def __init__(self, index, *, model: str, candidates: int) -> None:
        self._index = index
        self._candidates = candidates
        self._reranker = TextCrossEncoder(model_name=model)
        self.latencies: list[float] = []

    @property
    def config(self):
        return self._index.config

    @property
    def indexed_chunks(self):
        return self._index.indexed_chunks

    async def search(self, query: str, limit: int) -> list[Hit]:
        window = max(self._candidates, limit)
        hits = await self._index.search(query, window)
        started = time.perf_counter()
        scores = list(self._reranker.rerank(query, [hit.text for hit in hits]))
        self.latencies.append(time.perf_counter() - started)

        ranked = sorted(zip(hits, scores), key=lambda pair: pair[1], reverse=True)
        results: list[Hit] = []
        for hit, score in ranked[:limit]:
            metadata = dict(hit.metadata)
            metadata["dense_score"] = metadata.get("score")
            metadata["score"] = float(score)
            results.append(replace(hit, metadata=metadata))
        return results

    async def close(self) -> None:
        await self._index.close()
