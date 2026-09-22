"""Lexical retrieval (BM25) and Reciprocal Rank Fusion used by hybrid search.

The dense retriever stays authoritative for the relevance gate; BM25 only adds
lexical candidates and reorders them, which fixes cases where the same field
appears in several documents (e.g. "netto in busta" in many payslips) and the
distinguishing term is a rare one (e.g. "febbraio 22").
"""

from __future__ import annotations

import asyncio
import re
import time
from collections import OrderedDict
from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from rank_bm25 import BM25Okapi

from app.services.rag.vector_store import RetrievedChunk, collection_name

TOKEN_RE = re.compile(r"[0-9a-zàèéìòùáíóú]+")
SCROLL_PAGE = 1000
MAX_CACHED_TENANTS = 16
CACHE_REVALIDATE_SECONDS = 30

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
    """Build a BM25 index and search it (reference path, one-shot)."""
    if not corpus:
        return []
    bm25 = _build_bm25(corpus)
    return _rank(bm25, corpus, query, top_k)


@dataclass
class LexicalIndex:
    """Cached BM25 index for one tenant, valid for ``points_count`` points."""

    points_count: int
    corpus: list[CorpusChunk]
    bm25: BM25Okapi
    validated_at: float


_cache: OrderedDict[int, LexicalIndex] = OrderedDict()
_build_lock = asyncio.Lock()


def invalidate(tenant_id: int) -> None:
    """Drop a tenant's cached index after its collection changed."""
    _cache.pop(tenant_id, None)


def _fresh(entry: LexicalIndex) -> bool:
    if CACHE_REVALIDATE_SECONDS <= 0:
        return False
    return time.monotonic() - entry.validated_at < CACHE_REVALIDATE_SECONDS


async def get_lexical_index(
    client: AsyncQdrantClient, tenant_id: int
) -> LexicalIndex | None:
    """Return the tenant's BM25 index, rebuilding it when the point count changed.

    Writes invalidate the entry explicitly; the ``points_count`` check runs at
    most once per ``CACHE_REVALIDATE_SECONDS`` as a safety net, so the hot path
    is a dict lookup instead of a Qdrant round-trip. The LRU caps the memory.
    """
    entry = _cache.get(tenant_id)
    if entry is not None and _fresh(entry):
        _cache.move_to_end(tenant_id)
        return entry

    async with _build_lock:
        entry = _cache.get(tenant_id)
        if entry is not None and _fresh(entry):
            _cache.move_to_end(tenant_id)
            return entry
        return await _refresh_index(client, tenant_id)


async def _refresh_index(
    client: AsyncQdrantClient, tenant_id: int
) -> LexicalIndex | None:
    name = collection_name(tenant_id)
    if not await client.collection_exists(name):
        _cache.pop(tenant_id, None)
        return None

    points_count = (await client.count(name, exact=True)).count
    entry = _cache.get(tenant_id)
    if entry is not None and entry.points_count == points_count:
        entry.validated_at = time.monotonic()
        _cache.move_to_end(tenant_id)
        return entry

    corpus = await load_corpus(client, tenant_id)
    bm25 = await asyncio.to_thread(_build_bm25, corpus)
    index = LexicalIndex(
        points_count=points_count,
        corpus=corpus,
        bm25=bm25,
        validated_at=time.monotonic(),
    )
    _cache[tenant_id] = index
    _cache.move_to_end(tenant_id)
    while len(_cache) > MAX_CACHED_TENANTS:
        _cache.popitem(last=False)
    return index


def _build_bm25(corpus: list[CorpusChunk]) -> BM25Okapi:
    return BM25Okapi([tokenize(chunk.text) for chunk in corpus])


def _rank(
    bm25: BM25Okapi, corpus: list[CorpusChunk], query: str, top_k: int
) -> list[tuple[CorpusChunk, float]]:
    scores = bm25.get_scores(tokenize(query))
    ranked = sorted(range(len(corpus)), key=lambda index: scores[index], reverse=True)
    results: list[tuple[CorpusChunk, float]] = []
    for index in ranked[:top_k]:
        if scores[index] <= 0:
            break
        results.append((corpus[index], float(scores[index])))
    return results


def search_index(
    index: LexicalIndex, query: str, top_k: int
) -> list[tuple[CorpusChunk, float]]:
    """Search a cached index without re-tokenizing the corpus."""
    if not index.corpus:
        return []
    return _rank(index.bm25, index.corpus, query, top_k)


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
