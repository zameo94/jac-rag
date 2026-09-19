"""Retrieval benchmark runner.

The runner depends only on an abstract ``RetrievalIndex`` (query -> ranked hits)
and on the dataset schema. Swapping the embedding model, the vector store or the
chunker later requires neither changes to this file nor to the datasets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from benchmarks.retrieval.metrics import mean
from benchmarks.retrieval.schema import Category, QueryCase


@dataclass(frozen=True)
class Hit:
    key: str
    document_id: str
    text: str
    metadata: dict = field(default_factory=dict)


class RetrievalIndex(Protocol):
    def search(self, query: str, limit: int) -> list[Hit]:
        ...


class AsyncRetrievalIndex(Protocol):
    async def search(self, query: str, limit: int) -> list[Hit]:
        ...


@dataclass
class CaseOutcome:
    case_id: str
    query: str
    category: Category
    rank: int | None
    recall: dict[int, float]
    reciprocal_rank: float
    hits: list[Hit] = field(default_factory=list)


@dataclass
class Report:
    k_values: tuple[int, ...]
    outcomes: list[CaseOutcome] = field(default_factory=list)
    overall: dict[str, float] = field(default_factory=dict)
    per_category: dict[str, dict[str, float]] = field(default_factory=dict)
    per_category_counts: dict[str, int] = field(default_factory=dict)

    def render(self) -> str:
        lines = [f"cases: {len(self.outcomes)}  k={self.k_values}"]
        lines.append("OVERALL " + "  ".join(f"{k}={v:.4f}" for k, v in self.overall.items()))
        for category, scores in sorted(self.per_category.items()):
            count = self.per_category_counts.get(category, 0)
            lines.append(
                f"{category:14s} (n={count:2d}) "
                + "  ".join(f"{k}={v:.4f}" for k, v in scores.items())
            )
        return "\n".join(lines)


def matches(case: QueryCase, document_id: str, text: str) -> bool:
    """Chunk-level relevance.

    When both a document constraint and substrings are provided, a chunk must
    satisfy both: the document narrows the corpus, the substrings identify the
    chunk. With only document ids the judgment is document-level.
    """
    if case.relevant_document_ids and document_id not in case.relevant_document_ids:
        return False
    if case.expected_substrings:
        return any(
            substring.lower() in text.lower() for substring in case.expected_substrings
        )
    return True


def is_relevant(hit: Hit, case: QueryCase) -> bool:
    return matches(case, hit.document_id, hit.text)


def _scores(outcomes: list[CaseOutcome], k_values: tuple[int, ...]) -> dict[str, float]:
    scores = {"mrr": mean(outcome.reciprocal_rank for outcome in outcomes)}
    for k in k_values:
        scores[f"recall@{k}"] = mean(outcome.recall[k] for outcome in outcomes)
    return scores


def _build_report(
    cases: list[QueryCase],
    results: list[tuple[QueryCase, list[Hit]]],
    k_values: tuple[int, ...],
) -> Report:
    outcomes: list[CaseOutcome] = []
    for position, (case, hits) in enumerate(results):
        flags = [is_relevant(hit, case) for hit in hits]
        rank = next((i for i, relevant in enumerate(flags, start=1) if relevant), None)
        recall = {k: (1.0 if any(flags[:k]) else 0.0) for k in k_values}
        outcomes.append(
            CaseOutcome(
                case_id=case.case_id or f"case-{position}",
                query=case.query,
                category=case.category,
                rank=rank,
                recall=recall,
                reciprocal_rank=1.0 / rank if rank else 0.0,
                hits=hits,
            )
        )

    per_category: dict[str, dict[str, float]] = {}
    per_category_counts: dict[str, int] = {}
    for category in {outcome.category for outcome in outcomes}:
        subset = [outcome for outcome in outcomes if outcome.category is category]
        per_category[category.value] = _scores(subset, k_values)
        per_category_counts[category.value] = len(subset)

    return Report(
        k_values=k_values,
        outcomes=outcomes,
        overall=_scores(outcomes, k_values),
        per_category=per_category,
        per_category_counts=per_category_counts,
    )


def evaluate(
    cases: list[QueryCase],
    index: RetrievalIndex,
    k_values: tuple[int, ...] = (1, 5, 10),
) -> Report:
    if not cases:
        raise ValueError("no cases to evaluate")
    max_k = max(k_values)
    results = [(case, index.search(case.query, limit=max_k)) for case in cases]
    return _build_report(cases, results, k_values)


async def evaluate_async(
    cases: list[QueryCase],
    index: AsyncRetrievalIndex,
    k_values: tuple[int, ...] = (1, 5, 10),
) -> Report:
    if not cases:
        raise ValueError("no cases to evaluate")
    max_k = max(k_values)
    results = []
    for case in cases:
        hits = await index.search(case.query, limit=max_k)
        results.append((case, hits))
    return _build_report(cases, results, k_values)
