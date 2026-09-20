from app.services.rag.bm25 import (
    CorpusChunk,
    reciprocal_rank_fusion,
    search,
    tokenize,
)
from app.services.rag.vector_store import RetrievedChunk


def corpus() -> list[CorpusChunk]:
    return [
        CorpusChunk(1, 0, "Il netto in busta del cedolino marzo 22 e 1.700,00", "marzo.pdf"),
        CorpusChunk(2, 0, "Il netto in busta del cedolino febbraio 22 e 1.821,00", "febbraio.pdf"),
        CorpusChunk(3, 0, "Lettera di aumento retributivo del 2021", "aumento.pdf"),
    ]


def dense(document_id: int, chunk_index: int, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=document_id,
        chunk_index=chunk_index,
        text=f"text {document_id}",
        score=score,
        filename=f"doc{document_id}.pdf",
    )


def test_tokenize_lowercases_splits_and_drops_stopwords():
    assert tokenize("Il Netto in BUSTA, 1.821,00!") == ["netto", "busta", "1", "821", "00"]


def test_bm25_search_prefers_rare_term():
    results = search(corpus(), "quanto e il netto in busta febbraio 22", 3)

    assert results
    assert results[0][0].filename == "febbraio.pdf"
    assert results[0][1] > 0


def test_bm25_search_empty_corpus():
    assert search([], "anything", 5) == []


def test_rrf_prefers_chunk_present_in_both_lists():
    dense_hits = [dense(1, 0, 0.5), dense(2, 0, 0.4)]
    lexical_hits = [
        (CorpusChunk(2, 0, "b", "b.pdf"), 5.0),
        (CorpusChunk(3, 0, "c", "c.pdf"), 4.0),
    ]

    fused = reciprocal_rank_fusion(dense_hits, lexical_hits, limit=5, k=1)

    assert [(chunk.document_id, chunk.chunk_index) for chunk in fused] == [
        (2, 0),
        (1, 0),
        (3, 0),
    ]


def test_rrf_keeps_dense_score_and_includes_lexical_only():
    dense_hits = [dense(1, 0, 0.77)]
    lexical_hits = [(CorpusChunk(9, 2, "lexical", "l.pdf"), 3.0)]

    fused = reciprocal_rank_fusion(dense_hits, lexical_hits, limit=5, k=60)

    by_key = {(chunk.document_id, chunk.chunk_index): chunk for chunk in fused}
    assert by_key[(1, 0)].score == 0.77
    assert by_key[(9, 2)].score == 0.0
    assert by_key[(9, 2)].filename == "l.pdf"


def test_rrf_respects_limit():
    dense_hits = [dense(index, 0, 1.0 / index) for index in range(1, 6)]

    fused = reciprocal_rank_fusion(dense_hits, [], limit=2, k=60)

    assert len(fused) == 2
