import pytest
from qdrant_client import AsyncQdrantClient
from sqlmodel import select

from app.core.config import get_settings
from app.models import Document
from app.schemas.document import DocumentStatus
from app.services import storage
from app.services.rag import vector_store
from app.tasks.ingest import run_ingestion
from tests.fixtures import make_pdf


@pytest.fixture
async def qdrant():
    client = AsyncQdrantClient(":memory:")
    yield client
    await client.close()


async def make_document(
    session_factory,
    tenant_id=1,
    uploader_id=1,
    filename="doc.txt",
    mime="text/plain",
    content=b"contenuto di prova " * 20,
):
    storage_path = storage.save_upload(tenant_id, f"{filename}", content)
    async with session_factory() as session:
        document = Document(
            tenant_id=tenant_id,
            uploader_id=uploader_id,
            filename=filename,
            mime=mime,
            size=len(content),
            status=DocumentStatus.PENDING,
            storage_path=storage_path,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document.id


async def load_document(session_factory, document_id):
    async with session_factory() as session:
        return await session.get(Document, document_id)


async def test_ingestion_marks_document_ready(session_factory, qdrant):
    document_id = await make_document(session_factory)

    result = await run_ingestion(document_id, session_factory, qdrant)

    assert result == "ready"
    document = await load_document(session_factory, document_id)
    assert document.status is DocumentStatus.READY
    assert document.chunk_count > 0
    assert document.error is None


async def test_ingestion_stores_chunks_in_qdrant(session_factory, qdrant):
    document_id = await make_document(session_factory)

    await run_ingestion(document_id, session_factory, qdrant)

    assert await qdrant.collection_exists("tenant_1")
    info = await qdrant.get_collection("tenant_1")
    assert info.points_count == (await load_document(session_factory, document_id)).chunk_count


async def test_ingestion_sets_detected_language(session_factory, qdrant):
    document_id = await make_document(
        session_factory,
        content=("Questo documento è scritto in italiano con molte parole comuni. " * 10).encode(),
    )

    await run_ingestion(document_id, session_factory, qdrant)

    document = await load_document(session_factory, document_id)
    assert document.language == "it"


async def test_ingestion_replaces_previous_chunks(session_factory, qdrant):
    document_id = await make_document(session_factory)
    await run_ingestion(document_id, session_factory, qdrant)
    first_count = (await load_document(session_factory, document_id)).chunk_count

    await run_ingestion(document_id, session_factory, qdrant)

    info = await qdrant.get_collection("tenant_1")
    assert info.points_count == first_count


async def test_ingestion_marks_scanned_pdf_as_failed(session_factory, qdrant):
    document_id = await make_document(
        session_factory,
        filename="scan.pdf",
        mime="application/pdf",
        content=make_pdf(""),
    )

    result = await run_ingestion(document_id, session_factory, qdrant)

    assert result == "no_text_layer"
    document = await load_document(session_factory, document_id)
    assert document.status is DocumentStatus.FAILED
    assert document.error == "no_text_layer"


async def test_ingestion_marks_unparsable_document_as_failed(session_factory, qdrant):
    document_id = await make_document(
        session_factory,
        filename="broken.pdf",
        mime="application/pdf",
        content=b"%PDF-1.4 not really a pdf",
    )

    result = await run_ingestion(document_id, session_factory, qdrant)

    assert result == "failed"
    document = await load_document(session_factory, document_id)
    assert document.status is DocumentStatus.FAILED
    assert document.error.startswith("parse_error")


async def test_ingestion_returns_not_found_for_missing_document(session_factory, qdrant):
    result = await run_ingestion(999999, session_factory, qdrant)

    assert result == "not_found"


async def test_ingestion_isolates_tenants(session_factory, qdrant):
    doc_one = await make_document(session_factory, tenant_id=1, filename="one.txt")
    doc_two = await make_document(session_factory, tenant_id=2, filename="two.txt")

    await run_ingestion(doc_one, session_factory, qdrant)
    await run_ingestion(doc_two, session_factory, qdrant)

    assert await qdrant.collection_exists("tenant_1")
    assert await qdrant.collection_exists("tenant_2")
