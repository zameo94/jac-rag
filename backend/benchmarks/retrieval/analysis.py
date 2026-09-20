"""Failure analysis: separates ingestion failures from retrieval failures.

For every query that is NOT answered within top-k it checks, in order:

1. does the correct content exist in any indexed chunk?
   - no  -> ingestion/chunking failure
2. it exists, but is it retrieved at all (within max_k)?
   - no  -> retrieval failure
3. it is retrieved, but ranked below top-k?
   - yes -> ranking failure
"""

from __future__ import annotations

from dataclasses import dataclass, field

from benchmarks.retrieval.index import IndexedChunk
from benchmarks.retrieval.runner import Hit, Report, matches
from benchmarks.retrieval.schema import QueryCase

INGESTION = "ingestion/chunking"
RETRIEVAL = "retrieval"
RANKING = "ranking"
AMBIGUOUS_MATCH_THRESHOLD = 3


@dataclass
class FailureCase:
    case_id: str
    query: str
    category: str
    ground_truth: str
    classification: str
    rank: int | None
    indexed_matches: int
    hits: list[Hit] = field(default_factory=list)


@dataclass
class FailureAnalysis:
    ingestion: list[FailureCase] = field(default_factory=list)
    retrieval: list[FailureCase] = field(default_factory=list)
    ranking: list[FailureCase] = field(default_factory=list)
    ambiguous: list[FailureCase] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "ingestion/chunking": len(self.ingestion),
            "retrieval": len(self.retrieval),
            "ranking": len(self.ranking),
            "ambiguous_ground_truth": len(self.ambiguous),
        }


def ground_truth_repr(case: QueryCase) -> str:
    parts: list[str] = []
    if case.relevant_document_ids:
        parts.append("documents=" + ", ".join(case.relevant_document_ids))
    if case.expected_substrings:
        parts.append("substrings=" + " | ".join(case.expected_substrings))
    return "; ".join(parts)


def classify(
    case: QueryCase,
    hits: list[Hit],
    indexed_chunks: list[IndexedChunk],
    *,
    k: int,
    max_k: int,
) -> str | None:
    if any(matches(case, hit.document_id, hit.text) for hit in hits[:k]):
        return None
    if not any(matches(case, chunk.document_id, chunk.text) for chunk in indexed_chunks):
        return INGESTION
    if any(matches(case, hit.document_id, hit.text) for hit in hits[:max_k]):
        return RANKING
    return RETRIEVAL


@dataclass
class StructureCheck:
    case_id: str
    category: str
    retrieved: bool
    table_id: str | None
    row_indices: list | None
    source_block_ids: list | None
    page: int | None
    section: list | None


def structure_checks(
    cases: list[QueryCase],
    report: Report,
    indexed_chunks: list[IndexedChunk],
    categories: tuple = (),
) -> list[StructureCheck]:
    wanted = {category.value for category in categories}
    outcomes = {outcome.case_id: outcome for outcome in report.outcomes}
    checks: list[StructureCheck] = []

    for case in cases:
        if wanted and case.category.value not in wanted:
            continue
        outcome = outcomes.get(case.case_id or "")
        if outcome is None:
            continue
        relevant = next(
            (hit for hit in outcome.hits if matches(case, hit.document_id, hit.text)), None
        )
        retrieved = relevant is not None
        if relevant is None:
            chunk = next(
                (
                    candidate
                    for candidate in indexed_chunks
                    if matches(case, candidate.document_id, candidate.text)
                ),
                None,
            )
            metadata = chunk.metadata if chunk else {}
        else:
            metadata = relevant.metadata
        checks.append(
            StructureCheck(
                case_id=outcome.case_id,
                category=case.category.value,
                retrieved=retrieved,
                table_id=metadata.get("table_id"),
                row_indices=metadata.get("row_indices"),
                source_block_ids=metadata.get("source_block_ids"),
                page=metadata.get("page"),
                section=metadata.get("section"),
            )
        )

    return checks


def analyze(
    cases: list[QueryCase],
    report: Report,
    indexed_chunks: list[IndexedChunk],
    *,
    k: int = 5,
    max_k: int = 10,
) -> FailureAnalysis:
    outcomes = {outcome.case_id: outcome for outcome in report.outcomes}
    analysis = FailureAnalysis()

    for case in cases:
        outcome = outcomes.get(case.case_id or "")
        if outcome is None:
            continue
        matching = [
            chunk for chunk in indexed_chunks if matches(case, chunk.document_id, chunk.text)
        ]
        classification = classify(case, outcome.hits, indexed_chunks, k=k, max_k=max_k)

        if classification is not None:
            failure = FailureCase(
                case_id=outcome.case_id,
                query=case.query,
                category=case.category.value,
                ground_truth=ground_truth_repr(case),
                classification=classification,
                rank=outcome.rank,
                indexed_matches=len(matching),
                hits=outcome.hits[:max_k],
            )
            if classification == INGESTION:
                analysis.ingestion.append(failure)
            elif classification == RETRIEVAL:
                analysis.retrieval.append(failure)
            else:
                analysis.ranking.append(failure)

        if len(matching) > AMBIGUOUS_MATCH_THRESHOLD:
            analysis.ambiguous.append(
                FailureCase(
                    case_id=outcome.case_id,
                    query=case.query,
                    category=case.category.value,
                    ground_truth=ground_truth_repr(case),
                    classification="ambiguous_ground_truth",
                    rank=outcome.rank,
                    indexed_matches=len(matching),
                    hits=outcome.hits[:max_k],
                )
            )

    return analysis
