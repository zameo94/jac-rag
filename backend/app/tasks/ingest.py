from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.tkq import broker
from app.database import async_session_factory
from app.models import Document
from app.schemas.document import DocumentStatus
from app.services import storage
from app.services.rag import embeddings, vector_store
from app.services.rag.chunker import chunk_text
from app.services.rag.language import detect_language
from app.services.rag.parsers import get_parser

SessionFactory = async_sessionmaker[AsyncSession]


async def _mark_failed(session_factory: SessionFactory, document_id: int, error: str) -> None:
    async with session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return
        document.status = DocumentStatus.FAILED
        document.error = error[:500]
        session.add(document)
        await session.commit()


async def run_ingestion(
    document_id: int,
    session_factory: SessionFactory,
    qdrant_client,
) -> str:
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
        parsed = get_parser(mime)(content)
    except Exception as exc:
        await _mark_failed(session_factory, document_id, f"parse_error: {exc}")
        return "failed"

    if not parsed.has_text_layer():
        await _mark_failed(session_factory, document_id, "no_text_layer")
        return "no_text_layer"

    chunks = chunk_text(parsed.text, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        await _mark_failed(session_factory, document_id, "no_text_layer")
        return "no_text_layer"

    language = detect_language(parsed.text)
    texts = [chunk.text for chunk in chunks]
    vectors = embeddings.embed_texts(texts)

    await vector_store.delete_document_chunks(qdrant_client, tenant_id, document_id)
    await vector_store.upsert_chunks(
        qdrant_client,
        tenant_id,
        document_id,
        filename,
        [(chunk.index, chunk.text) for chunk in chunks],
        vectors,
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
