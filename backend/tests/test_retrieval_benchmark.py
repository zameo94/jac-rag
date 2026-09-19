from pathlib import Path

import pytest

from benchmarks.retrieval.analysis import (
    INGESTION,
    RANKING,
    RETRIEVAL,
    classify,
)
from benchmarks.retrieval.index import IndexedChunk
from benchmarks.retrieval.metrics import mean, recall_at_k, reciprocal_rank
from benchmarks.retrieval.runner import Hit, evaluate, is_relevant, matches
from benchmarks.retrieval.schema import (
    Category,
    QueryCase,
    load_dataset,
    load_queries,
)

SAMPLE_DIR = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "retrieval"
    / "data"
    / "sample"
)


# --------------------------------------------------------------------------- #
# Metrics                                                                      #
# --------------------------------------------------------------------------- #


def test_recall_at_k_found_within_k():
    assert recall_at_k(["a", "b", "c"], {"b"}, 2) == 1.0


def test_recall_at_k_not_found_within_k():
    assert recall_at_k(["a", "b", "c"], {"c"}, 2) == 0.0


def test_recall_at_k_partial_with_multiple_relevant():
    assert recall_at_k(["a", "b", "c"], {"a", "c"}, 2) == 0.5


def test_recall_at_k_rejects_empty_relevant():
    with pytest.raises(ValueError):
        recall_at_k(["a"], set(), 1)


def test_reciprocal_rank_first_relevant():
    assert reciprocal_rank(["a", "b", "c"], {"b"}) == 0.5


def test_reciprocal_rank_none():
    assert reciprocal_rank(["a", "b"], {"z"}) == 0.0


def test_reciprocal_rank_top():
    assert reciprocal_rank(["z", "a"], {"z"}) == 1.0


def test_mean_rejects_empty():
    with pytest.raises(ValueError):
        mean([])


# --------------------------------------------------------------------------- #
# Schema                                                                       #
# --------------------------------------------------------------------------- #


def test_query_case_requires_ground_truth():
    with pytest.raises(ValueError):
        QueryCase(query="x", category=Category.PROSE)


def test_load_sample_dataset():
    dataset = load_dataset(SAMPLE_DIR)

    assert dataset.name == "sample"
    assert len(dataset.documents) == 5
    assert len(dataset.queries) == 29
    categories = {case.category for case in dataset.queries}
    assert Category.TABLE in categories
    assert Category.CODES in categories
    assert Category.LEGAL in categories
    assert Category.TECHNICAL in categories


def test_dataset_documents_exist():
    dataset = load_dataset(SAMPLE_DIR)

    for document in dataset.documents:
        assert (dataset.base_dir / document.path).exists()


def test_load_queries_from_file(tmp_path):
    path = tmp_path / "queries.jsonl"
    path.write_text(
        '{"query": "x", "category": "prose", "expected_substrings": ["y"]}\n',
        encoding="utf-8",
    )

    queries = load_queries(path)

    assert len(queries) == 1
    assert queries[0].query == "x"
    assert queries[0].category is Category.PROSE


def test_resolve_dataset_from_single_document(tmp_path):
    from benchmarks.run_baseline import resolve_dataset

    document = tmp_path / "catalogo.pdf"
    document.write_bytes(b"%PDF-1.4\n")

    dataset = resolve_dataset(document, None)

    assert len(dataset.documents) == 1
    assert dataset.documents[0].document_id == "catalogo"
    assert dataset.documents[0].mime == "application/pdf"
    assert dataset.queries == ()


def test_resolve_dataset_from_directory_of_documents(tmp_path):
    from benchmarks.run_baseline import resolve_dataset

    (tmp_path / "a.md").write_text("# a", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("b", encoding="utf-8")
    (tmp_path / "skip.bin").write_bytes(b"\x00")

    dataset = resolve_dataset(tmp_path, None)

    assert {d.document_id for d in dataset.documents} == {"a", "notes"}


def test_resolve_dataset_attaches_queries_to_single_document(tmp_path):
    from benchmarks.run_baseline import resolve_dataset

    document = tmp_path / "doc.md"
    document.write_text("# doc", encoding="utf-8")
    queries = tmp_path / "q.jsonl"
    queries.write_text(
        '{"query": "q", "category": "prose", "relevant_document_ids": ["doc"]}\n',
        encoding="utf-8",
    )

    dataset = resolve_dataset(document, queries)

    assert len(dataset.queries) == 1
    assert dataset.documents[0].document_id == "doc"


# --------------------------------------------------------------------------- #
# Runner                                                                       #
# --------------------------------------------------------------------------- #


class FakeIndex:
    def __init__(self, results: dict[str, list[Hit]]):
        self.results = results

    def search(self, query: str, limit: int) -> list[Hit]:
        return self.results.get(query, [])[:limit]


def hit(key: str, document_id: str, text: str) -> Hit:
    return Hit(key=key, document_id=document_id, text=text)


def test_is_relevant_by_document_id():
    case = QueryCase(query="q", category=Category.PROSE, relevant_document_ids=("doc1",))

    assert is_relevant(hit("k", "doc1", "anything"), case) is True
    assert is_relevant(hit("k", "doc2", "anything"), case) is False


def test_is_relevant_by_substring_case_insensitive():
    case = QueryCase(query="q", category=Category.NUMBERS, expected_substrings=("649,00",))

    assert is_relevant(hit("k", "doc", "Prezzo: 649,00 EUR"), case) is True
    assert is_relevant(hit("k", "doc", "Prezzo: 799,90 EUR"), case) is False


def test_evaluate_computes_recall_and_mrr():
    case_a = QueryCase(query="qa", category=Category.TABLE, expected_substrings=("target",))
    case_b = QueryCase(query="qb", category=Category.PROSE, expected_substrings=("missing",))
    index = FakeIndex(
        {
            "qa": [hit("1", "d", "noise"), hit("2", "d", "the target value")],
            "qb": [hit("3", "d", "nothing relevant")],
        }
    )

    report = evaluate([case_a, case_b], index, k_values=(1, 5))

    outcome_a = next(o for o in report.outcomes if o.case_id == "case-0")
    assert outcome_a.rank == 2
    assert outcome_a.recall[1] == 0.0
    assert outcome_a.recall[5] == 1.0
    assert outcome_a.reciprocal_rank == 0.5

    assert report.overall["recall@1"] == 0.0
    assert report.overall["recall@5"] == 0.5
    assert report.overall["mrr"] == 0.25
    assert set(report.per_category) == {"table", "prose"}


def test_evaluate_rejects_empty_cases():
    with pytest.raises(ValueError):
        evaluate([], FakeIndex({}))


def test_report_render_contains_sections():
    index = FakeIndex({"qa": [hit("1", "d", "target")]})
    case = QueryCase(query="qa", category=Category.TABLE, expected_substrings=("target",))

    rendered = evaluate([case], index, k_values=(1,)).render()

    assert "OVERALL" in rendered
    assert "table" in rendered


def test_matches_requires_both_document_and_substring():
    case = QueryCase(
        query="q",
        category=Category.TABLE,
        relevant_document_ids=("doc",),
        expected_substrings=("target",),
    )

    assert matches(case, "doc", "the target value") is True
    assert matches(case, "doc", "something else") is False
    assert matches(case, "other", "the target value") is False


def indexed(point_id: int, document_id: str, text: str) -> IndexedChunk:
    return IndexedChunk(
        point_id=point_id, document_id=document_id, chunk_index=0, text=text, metadata={}
    )


def case_with_target() -> QueryCase:
    return QueryCase(
        query="q",
        category=Category.TABLE,
        relevant_document_ids=("doc",),
        expected_substrings=("target",),
    )


def test_classify_success_returns_none():
    case = case_with_target()
    hits = [hit("1", "doc", "the target")]

    assert classify(case, hits, [indexed(1, "doc", "the target")], k=1, max_k=10) is None


def test_classify_ingestion_when_content_missing():
    case = case_with_target()
    hits = [hit("1", "doc", "unrelated text")]

    assert classify(case, hits, [indexed(1, "doc", "unrelated text")], k=1, max_k=10) == INGESTION


def test_classify_retrieval_when_not_retrieved():
    case = case_with_target()
    hits = [hit("1", "doc", "noise"), hit("2", "doc", "more noise")]

    assert (
        classify(case, hits, [indexed(3, "doc", "the target")], k=1, max_k=10) == RETRIEVAL
    )


def test_classify_ranking_when_retrieved_below_top_k():
    case = case_with_target()
    hits = [hit("1", "doc", "noise"), hit("2", "doc", "the target")]

    assert classify(case, hits, [indexed(2, "doc", "the target")], k=1, max_k=10) == RANKING

