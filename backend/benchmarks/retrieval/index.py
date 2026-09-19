"""Adapter: benchmark RetrievalIndex -> the real application retrieval path.

It reuses the exact application components, in the same order as ingestion:

    parser -> normalize -> chunk_document -> embeddings.embed_texts -> upsert
    query  -> embeddings.embed_query -> vector_store.search_chunks

No second search implementation exists here. Metadata is read from the chunks we
indexed (keyed by the same deterministic point id used by ``upsert_chunks``), so
``search_chunks`` itself is never modified.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qdrant_client import AsyncQdrantClient

from app.core.config import get_settings
from app.services.rag import embeddings, vector_store
from app.services.rag.chunker import ChunkingConfig, chunk_document
from app.services.rag.normalize import normalize_document
from app.services.rag.parsers import get_parser
from app.tasks.ingest import _metadata_payload
from benchmarks.retrieval.runner import Hit
from benchmarks.retrieval.schema import BenchmarkDataset


@dataclass(frozen=True)
class IndexedChunk:
    point_id: int
    document_id: str
    chunk_index: int
    text: str
    metadata: dict

    def as_hit(self, score: float) -> Hit:
        metadata = dict(self.metadata)
        metadata.update(
            {"score": score, "chunk_index": self.chunk_index, "point_id": self.point_id}
        )
        return Hit(
            key=str(self.point_id),
            document_id=self.document_id,
            text=self.text,
            metadata=metadata,
        )


@dataclass(frozen=True)
class BenchmarkConfig:
    embedding_model: str
    embedding_dim: int
    distance: str
    collection: str
    chunk_target_size: int
    chunk_max_size: int
    chunk_overlap: int
    table_context: bool
    section_context: bool
    include_metadata: bool
    relevance_threshold: float
    retrieval_limit: int


class QdrantRetrievalIndex:
    def __init__(
        self,
        client: AsyncQdrantClient,
        tenant_id: int,
        chunks: list[IndexedChunk],
        config: BenchmarkConfig,
    ) -> None:
        self._client = client
        self._tenant_id = tenant_id
        self._chunks = chunks
        self._by_id = {chunk.point_id: chunk for chunk in chunks}
        self.config = config

    @property
    def indexed_chunks(self) -> list[IndexedChunk]:
        return list(self._chunks)

    @classmethod
    async def build(
        cls,
        dataset: BenchmarkDataset,
        *,
        tenant_id: int = 1,
        retrieval_limit: int = 10,
    ) -> "QdrantRetrievalIndex":
        settings = get_settings()
        chunking = ChunkingConfig(
            target_size=settings.chunk_size,
            max_size=settings.chunk_max_size,
            overlap=settings.chunk_overlap,
            table_context=settings.chunk_table_context,
            section_context=settings.chunk_section_context,
            include_metadata=settings.chunk_include_metadata,
        )
        client = AsyncQdrantClient(":memory:")
        await vector_store.ensure_collection(client, tenant_id)

        chunks: list[IndexedChunk] = []
        for position, document in enumerate(dataset.documents, start=1):
            content = Path(dataset.base_dir / document.path).read_bytes()
            parsed = get_parser(document.mime).parse(content, source=document.document_id)
            document_ir = normalize_document(parsed)
            document_chunks = chunk_document(document_ir, chunking)
            vectors = embeddings.embed_texts([chunk.text for chunk in document_chunks])
            metadatas = [_metadata_payload(chunk.metadata) for chunk in document_chunks]
            await vector_store.upsert_chunks(
                client,
                tenant_id,
                position,
                document.document_id,
                [(chunk.index, chunk.text) for chunk in document_chunks],
                vectors,
                metadatas=metadatas,
            )
            for chunk, metadata in zip(document_chunks, metadatas):
                chunks.append(
                    IndexedChunk(
                        point_id=vector_store._point_id(position, chunk.index),
                        document_id=document.document_id,
                        chunk_index=chunk.index,
                        text=chunk.text,
                        metadata=metadata,
                    )
                )

        config = BenchmarkConfig(
            embedding_model=settings.embedding_model,
            embedding_dim=settings.embedding_dim,
            distance="Cosine",
            collection=vector_store.collection_name(tenant_id),
            chunk_target_size=settings.chunk_size,
            chunk_max_size=settings.chunk_max_size,
            chunk_overlap=settings.chunk_overlap,
            table_context=settings.chunk_table_context,
            section_context=settings.chunk_section_context,
            include_metadata=settings.chunk_include_metadata,
            relevance_threshold=settings.relevance_threshold,
            retrieval_limit=retrieval_limit,
        )
        return cls(client, tenant_id, chunks, config)

    async def search(self, query: str, limit: int) -> list[Hit]:
        vector = embeddings.embed_query(query)
        results = await vector_store.search_chunks(self._client, self._tenant_id, vector, limit)
        hits: list[Hit] = []
        for result in results:
            point_id = vector_store._point_id(result.document_id, result.chunk_index)
            indexed = self._by_id.get(point_id)
            if indexed is not None:
                hits.append(indexed.as_hit(result.score))
            else:  # pragma: no cover - defensive
                hits.append(
                    Hit(
                        key=str(point_id),
                        document_id=str(result.document_id),
                        text=result.text,
                        metadata={"score": result.score, "chunk_index": result.chunk_index},
                    )
                )
        return hits

    async def close(self) -> None:
        await self._client.close()
