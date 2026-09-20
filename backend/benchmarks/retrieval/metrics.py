"""Model-independent retrieval metrics.

The benchmark core knows nothing about embeddings, Qdrant or chunking: it only
sees ranked lists of keys and relevance judgments. This keeps the benchmark
stable when the embedding model or the index changes.
"""

from __future__ import annotations

from collections.abc import Iterable


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant items found in the top ``k``."""
    if not relevant:
        raise ValueError("relevant set must not be empty")
    if k <= 0:
        raise ValueError("k must be positive")
    return len(set(ranked[:k]) & relevant) / len(relevant)


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    """1 / rank of the first relevant item, or 0.0 if none is retrieved."""
    if not relevant:
        raise ValueError("relevant set must not be empty")
    for rank, key in enumerate(ranked, start=1):
        if key in relevant:
            return 1.0 / rank
    return 0.0


def mean(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        raise ValueError("cannot average an empty sequence")
    return sum(items) / len(items)
