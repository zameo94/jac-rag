"""Lexical retrieval (BM25) and Reciprocal Rank Fusion used by hybrid search.

The dense retriever stays authoritative for the relevance gate; BM25 only adds
lexical candidates and reorders them, which fixes cases where the same field
appears in several documents (e.g. "netto in busta" in many payslips) and the
distinguishing term is a rare one (e.g. "febbraio 22").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from rank_bm25 import BM25Okapi

from app.services.rag.vector_store import RetrievedChunk, collection_name

TOKEN_RE = re.compile(r"[0-9a-zàèéìòùáíóú]+")
SCROLL_PAGE = 1000

STOPWORDS = frozenset(
    {
        "a", "ad", "al", "alla", "alle", "agli", "allo", "anche", "ancora",
        "che", "chi", "ci", "come", "con", "cui", "da", "dal", "dalla", "dai",
        "dalle", "dagli", "dei", "del", "della", "delle", "degli", "dello",
        "di", "dove", "e", "ed", "era", "essere", "fa", "fra", "gli", "ha",
        "hai", "hanno", "ho", "i", "il", "in", "io", "la", "le", "lo", "ma",
        "mi", "mio", "nei", "nel", "nella", "nelle", "negli", "nello", "non",
        "o", "per", "piu", "più", "quale", "quali", "quando", "quanto", "quanta",
        "quanti", "quante", "quello", "questa", "queste", "questi", "questo",
        "se", "si", "sono", "su", "sul", "sulla", "sulle", "sui", "sugli",
        "sullo", "tra", "tu", "tuo", "un", "una", "uno", "vi", "voi",
        "the", "a", "an", "and", "are", "as", "at", "be", "been", "by", "did",
        "do", "does", "for", "from", "how", "i", "in", "is", "it", "its",
        "of", "on", "or", "that", "the", "their", "these", "this", "those",
        "to", "was", "we", "were", "what", "when", "where", "which", "who",
        "whom", "with", "you",
    }
)


@dataclass(frozen=True)
class CorpusChunk:
    document_id: int
    chunk_index: int
    text: str
    filename: str


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS]


async def load_corpus(client: AsyncQdrantClient, tenant_id: int) -> list[CorpusChunk]:
    name = collection_name(tenant_id)
    if not await client.collection_exists(name):
        return []
    corpus: list[CorpusChunk] = []
    offset = None
    while True:
        records, offset = await client.scroll(
            name, limit=SCROLL_PAGE, with_payload=True, offset=offset
        )
        for record in records:
            payload = record.payload or {}
            text = payload.get("text")
            if not text:
                continue
            corpus.append(
                CorpusChunk(
                    document_id=int(payload.get("document_id", 0)),
                    chunk_index=int(payload.get("chunk_index", 0)),
                    text=text,
                    filename=str(payload.get("filename", "")),
                )
            )
        if offset is None:
            break
    return corpus


def search(
    corpus: list[CorpusChunk], query: str, top_k: int
) -> list[tuple[CorpusChunk, float]]:
    if not corpus:
        return []
    tokenized = [tokenize(chunk.text) for chunk in corpus]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(tokenize(query))
    ranked = sorted(range(len(corpus)), key=lambda index: scores[index], reverse=True)
    results: list[tuple[CorpusChunk, float]] = []
    for index in ranked[:top_k]:
        if scores[index] <= 0:
            break
        results.append((corpus[index], float(scores[index])))
    return results


def _key(chunk: RetrievedChunk) -> tuple[int, int]:
    return (chunk.document_id, chunk.chunk_index)


def reciprocal_rank_fusion(
    dense: list[RetrievedChunk],
    lexical: list[tuple[CorpusChunk, float]],
    *,
    limit: int,
    k: int,
) -> list[RetrievedChunk]:
    scores: dict[tuple[int, int], float] = {}
    items: dict[tuple[int, int], RetrievedChunk] = {}

    for rank, chunk in enumerate(dense, start=1):
        key = _key(chunk)
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        items[key] = chunk

    for rank, (chunk, _) in enumerate(lexical, start=1):
        key = (chunk.document_id, chunk.chunk_index)
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        if key not in items:
            items[key] = RetrievedChunk(
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                score=0.0,
                filename=chunk.filename,
            )

    ordered = sorted(items.values(), key=lambda chunk: scores[_key(chunk)], reverse=True)
    return ordered[:limit]
