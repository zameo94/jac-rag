"""Schema and (de)serialization for the retrieval benchmark dataset."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Category(str, Enum):
    PROSE = "prose"
    HEADING = "heading"
    TABLE = "table"
    NUMBERS = "numbers"
    CODES = "codes"
    PROPER_NOUNS = "proper_nouns"
    SEMANTIC = "semantic"
    LEGAL = "legal"
    TECHNICAL = "technical"


@dataclass(frozen=True)
class DocumentSpec:
    """A corpus document. ``path`` points to a file relative to the dataset."""

    document_id: str
    mime: str
    path: str


@dataclass(frozen=True)
class QueryCase:
    """A query with its ground truth.

    Relevance is judged by document id and/or by required substrings; at least
    one of the two must be provided.
    """

    query: str
    category: Category
    relevant_document_ids: tuple[str, ...] = ()
    expected_substrings: tuple[str, ...] = ()
    case_id: str | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.relevant_document_ids and not self.expected_substrings:
            raise ValueError(f"query '{self.query}' has no ground truth")


@dataclass(frozen=True)
class BenchmarkDataset:
    name: str
    base_dir: Path
    documents: tuple[DocumentSpec, ...]
    queries: tuple[QueryCase, ...]


def _load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            records.append(json.loads(line))
    return records


def query_from_record(record: dict) -> QueryCase:
    return QueryCase(
        case_id=record.get("case_id"),
        query=record["query"],
        category=Category(record["category"]),
        relevant_document_ids=tuple(record.get("relevant_document_ids", [])),
        expected_substrings=tuple(record.get("expected_substrings", [])),
        metadata=record.get("metadata", {}),
    )


def load_queries(path: str | Path) -> tuple[QueryCase, ...]:
    return tuple(query_from_record(record) for record in _load_jsonl(Path(path)))


def load_dataset(directory: str | Path) -> BenchmarkDataset:
    directory = Path(directory)
    meta = json.loads((directory / "dataset.json").read_text(encoding="utf-8"))
    documents = tuple(
        DocumentSpec(
            document_id=record["document_id"],
            mime=record["mime"],
            path=record["path"],
        )
        for record in _load_jsonl(directory / "documents.jsonl")
    )
    queries = load_queries(directory / "queries.jsonl")
    return BenchmarkDataset(
        name=meta["name"], base_dir=directory, documents=documents, queries=queries
    )
