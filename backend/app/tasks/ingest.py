import logging

from app.core.config import get_settings
from app.core.tkq import broker
from app.database import async_session_factory
from app.models import Document
from app.schemas.document import DocumentStatus
from app.services import storage
from app.services.rag import embeddings, vector_store
from app.services.rag.chunker import ChunkingConfig, ChunkMetadata, chunk_document
from app.services.rag.language import detect_language
from app.services.rag.normalize import normalize_document
from app.services.rag.parsers import get_parser

logger = logging.getLogger(__name__)


def _chunking_config() -> ChunkingConfig:
    settings = get_settings()
    return ChunkingConfig(
        target_size=settings.chunk_size,
        max_size=settings.chunk_max_size,
        overlap=settings.chunk_overlap,
        table_context=settings.chunk_table_context,
        section_context=settings.chunk_section_context,
        include_metadata=settings.chunk_include_metadata,
    )


def _metadata_payload(metadata: ChunkMetadata) -> dict[str, object]:
    return {
        "page": metadata.page,
        "block_type": metadata.block_type.value if metadata.block_type else None,
        "section": list(metadata.section) if metadata.section else None,
        "table_id": metadata.table_id,
        "row_indices": list(metadata.row_indices) if metadata.row_indices else None,
        "source_block_ids": list(metadata.source_block_ids) if metadata.source_block_ids else None,
        "oversized": metadata.oversized,
    }


async def _mark_failed(session_factory, document_id: int, error: str) -> None:
    async with session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return
        document.status = DocumentStatus.FAILED
        document.error = error[:500]
        session.add(document)
        await session.commit()


async def run_ingestion(document_id, session_factory, qdrant_client) -> str:
    settings = get_settings()

    async with session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return "not_found"

        document.status = DocumentStatus.PROCESSING
        document.error = None
        session.add(document)
        await session.commit()
        await session.refresh(document)

        tenant_id = document.tenant_id
        filename = document.filename
        storage_path = document.storage_path
        mime = document.mime

    try:
        content = storage.read_file(storage_path)
        parsed = get_parser(mime).parse(content, source=filename)
        document_ir = normalize_document(parsed)
        if settings.drop_repeated_layout:
            document_ir.blocks = [block for block in document_ir.blocks if not block.repeated_layout]
    except Exception as exc:
        await _mark_failed(session_factory, document_id, f"parse_error: {exc}")
        return "failed"

    diagnostics = document_ir.diagnostics
    diagnostics.repeated_layout_blocks = sum(
        1 for block in document_ir.blocks if block.repeated_layout
    )
    if settings.parser_debug:
        logger.info("extraction diagnostics source=%s %s", filename, diagnostics.as_dict())
    else:
        diagnostics.log(logger, source=filename)

    if not document_ir.has_text_layer():
        await _mark_failed(session_factory, document_id, "no_text_layer")
        return "no_text_layer"

    chunks = chunk_document(document_ir, _chunking_config())
    if not chunks:
        await _mark_failed(session_factory, document_id, "no_text_layer")
        return "no_text_layer"

    language = detect_language(document_ir.text)
    texts = [chunk.text for chunk in chunks]
    vectors = embeddings.embed_texts(texts)
    metadatas = [_metadata_payload(chunk.metadata) for chunk in chunks]

    await vector_store.delete_document_chunks(qdrant_client, tenant_id, document_id)
    await vector_store.upsert_chunks(
        qdrant_client,
        tenant_id,
        document_id,
        filename,
        [(chunk.index, chunk.text) for chunk in chunks],
        vectors,
        metadatas=metadatas,
    )

    async with session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return "not_found"
        document.status = DocumentStatus.READY
        document.language = language
        document.chunk_count = len(chunks)
        document.error = None
        session.add(document)
        await session.commit()

    return "ready"


@broker.task(retries=2, retry_delay=10)
async def ingest_document(document_id: int) -> str:
    client = vector_store.get_qdrant_client()
    try:
        return await run_ingestion(document_id, async_session_factory, client)
    finally:
        await client.close()
