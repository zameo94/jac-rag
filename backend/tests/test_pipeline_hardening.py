import pdfplumber
import pytest
from qdrant_client import AsyncQdrantClient

from app.models import Document as DocumentModel
from app.schemas.document import DocumentStatus
from app.services import storage
from app.services.rag.chunker import ChunkingConfig, chunk_document
from app.services.rag.ir import TableBlock
from app.services.rag.normalize import normalize_document
from app.services.rag.parsers import parse_docx, parse_pdf
from app.tasks.ingest import run_ingestion
from tests.fixtures import build_pdf, make_docx_document

CONFIG = ChunkingConfig(target_size=200, max_size=400, overlap=20)


def sample_blocks():
    return [
        ("title", "Documento di prova"),
        ("heading", "Capitolo 1"),
        ("text", "Paragrafo con contenuto."),
        ("table", ["Modello", "Prezzo"], [["A1", "10,00"], ["B2", "20,00"]], True),
    ]


# --------------------------------------------------------------------------- #
# Determinism                                                                  #
# --------------------------------------------------------------------------- #


def test_pdf_ir_is_deterministic():
    pdf = build_pdf(sample_blocks())

    first = normalize_document(parse_pdf(pdf))
    second = normalize_document(parse_pdf(pdf))

    assert first.text == second.text
    assert [block.source_block_id for block in first.blocks] == [
        block.source_block_id for block in second.blocks
    ]
    assert [block.section_path for block in first.blocks] == [
        block.section_path for block in second.blocks
    ]
    assert [block.order for block in first.blocks] == [block.order for block in second.blocks]


def test_chunks_are_deterministic():
    pdf = build_pdf(sample_blocks())
    document = normalize_document(parse_pdf(pdf))

    first = chunk_document(document, CONFIG)
    second = chunk_document(document, CONFIG)

    assert [chunk.text for chunk in first] == [chunk.text for chunk in second]
    assert [chunk.metadata for chunk in first] == [chunk.metadata for chunk in second]


def test_table_row_metadata_has_no_duplicate_source_ids():
    pdf = build_pdf(
        [("table", ["Nome", "Valore"], [["A", "1"], ["B", "2"], ["C", "3"]], True)]
    )
    document = normalize_document(parse_pdf(pdf))

    chunks = chunk_document(document, CONFIG)
    table_chunks = [chunk for chunk in chunks if chunk.metadata.table_id]

    assert table_chunks
    for chunk in table_chunks:
        assert len(chunk.metadata.source_block_ids) == 1
        assert len(set(chunk.metadata.row_indices)) == len(chunk.metadata.row_indices)


def test_list_item_source_ids_are_unique():
    document = normalize_document(
        parse_docx(make_docx_document([("list", ["uno", "due", "tre"])]))
    )

    items = document.blocks[0].items
    ids = [item.source_block_id for item in items]
    assert len(set(ids)) == 3


# --------------------------------------------------------------------------- #
# Failure isolation                                                            #
# --------------------------------------------------------------------------- #


def test_pdf_page_failure_does_not_lose_other_pages(monkeypatch):
    pdf = build_pdf(
        [
            ("text", "Contenuto pagina uno."),
            ("pagebreak",),
            ("text", "Contenuto pagina due."),
            ("pagebreak",),
            ("text", "Contenuto pagina tre."),
        ]
    )
    original = pdfplumber.page.Page.extract_text_lines

    def flaky(self, *args, **kwargs):
        if self.page_number == 2:
            raise RuntimeError("boom")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pdfplumber.page.Page, "extract_text_lines", flaky)

    document = parse_pdf(pdf)

    assert "pagina uno" in document.text
    assert "pagina tre" in document.text
    assert any("failed" in warning for warning in document.diagnostics.warnings)


def test_docx_block_failure_does_not_lose_other_blocks(monkeypatch):
    blocks = [
        ("heading", "Titolo", 1),
        ("table", ["A", "B"], [["1", "2"]]),
        ("paragraph", "Paragrafo finale."),
    ]
    content = make_docx_document(blocks)

    def broken_table(table, sequence):
        raise RuntimeError("table boom")

    monkeypatch.setattr("app.services.rag.parsers.docx._table_block", broken_table)

    document = parse_docx(content)

    assert "Titolo" in document.text
    assert "Paragrafo finale." in document.text
    assert any("skipped" in warning for warning in document.diagnostics.warnings)


@pytest.fixture
async def qdrant():
    client = AsyncQdrantClient(":memory:")
    yield client
    await client.close()


async def test_ingestion_stores_full_metadata_payload(session_factory, qdrant):
    content = (
        "# Listino\n\n| Modello | Prezzo |\n| --- | --- |\n| A1 | 10,00 |\n"
    ).encode()
    storage_path = storage.save_upload(1, "meta.md", content)
    async with session_factory() as session:
        document = DocumentModel(
            workspace_id=1,
            uploader_id=1,
            filename="meta.md",
            mime="text/markdown",
            size=len(content),
            status=DocumentStatus.PENDING,
            storage_path=storage_path,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        document_id = document.id

    await run_ingestion(document_id, session_factory, qdrant)

    points, _ = await qdrant.scroll("workspace_1", limit=100, with_payload=True)
    row_points = [
        point
        for point in points
        if point.payload and point.payload.get("block_type") == "table_row"
    ]
    assert row_points
    payload = row_points[0].payload
    for key in (
        "document_id",
        "chunk_index",
        "text",
        "filename",
        "page",
        "block_type",
        "section",
        "table_id",
        "row_indices",
        "source_block_ids",
        "oversized",
    ):
        assert key in payload, key
    assert payload["section"] == ["Listino"]
    assert payload["source_block_ids"] == ["block-1"]
    assert payload["oversized"] is False
