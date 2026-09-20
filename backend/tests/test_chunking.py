from app.services.rag.chunker import ChunkingConfig, chunk_document
from app.services.rag.ir import (
    BlockType,
    Document,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    TableBlock,
    TableCell,
    TableRow,
)
from app.services.rag.normalize import normalize_document
from app.services.rag.parsers import parse_markdown


def make_config(**overrides) -> ChunkingConfig:
    values = {"target_size": 200, "max_size": 400, "overlap": 20}
    values.update(overrides)
    return ChunkingConfig(**values)


def make_table_document(row_count: int, *, caption: str | None = None) -> Document:
    rows = []
    for index in range(row_count):
        rows.append(
            TableRow(
                index=index,
                cells=[
                    TableCell(text=f"Nome{index}", column_index=0, header="Nome"),
                    TableCell(text=f"Valore{index}", column_index=1, header="Valore"),
                ],
            )
        )
    table = TableBlock(
        table_id="t1",
        header=["Nome", "Valore"],
        rows=rows,
        caption=caption,
        page=3,
    )
    return normalize_document(Document(page_count=3, blocks=[table]))


def test_table_row_is_never_split_across_chunks():
    document = make_table_document(5)

    chunks = chunk_document(document, make_config(target_size=60, max_size=400))

    assert len(chunks) > 1
    for chunk in chunks:
        for name_line in [line for line in chunk.text.splitlines() if line.startswith("Nome")]:
            assert "Valore" in chunk.text


def test_all_table_rows_survive_chunking():
    row_count = 12
    document = make_table_document(row_count)

    chunks = chunk_document(document, make_config(target_size=120, max_size=400))

    combined = "\n".join(chunk.text for chunk in chunks)
    for index in range(row_count):
        assert f"Nome{index}" in combined
        assert f"Valore{index}" in combined


def test_row_metadata_is_preserved():
    document = make_table_document(4)

    chunks = chunk_document(document, make_config(target_size=120, max_size=400))

    row_indices = [row for chunk in chunks for row in chunk.metadata.row_indices]
    assert row_indices == [0, 1, 2, 3]
    assert all(chunk.metadata.table_id == "t1" for chunk in chunks)
    assert all(chunk.metadata.page == 3 for chunk in chunks)


def test_table_context_is_included():
    document = make_table_document(2, caption="Smartphone")

    chunks = chunk_document(document, make_config(target_size=200, max_size=400))

    assert "Tabella: Smartphone" in chunks[0].text
    assert "Colonne: Nome, Valore" in chunks[0].text


def test_table_context_can_be_disabled():
    document = make_table_document(2, caption="Smartphone")

    chunks = chunk_document(
        document, make_config(target_size=200, max_size=400, table_context=False)
    )

    assert "Tabella: Smartphone" not in chunks[0].text


def test_orphan_heading_is_a_standalone_chunk():
    document = normalize_document(
        Document(page_count=1, blocks=[Heading(text="Capitolo 1", level=1)])
    )

    chunks = chunk_document(document, make_config())

    assert len(chunks) == 1
    assert chunks[0].text == "Contenuto:\nTitolo: Capitolo 1"
    assert chunks[0].metadata.block_type is BlockType.HEADING


def test_heading_context_is_propagated_to_following_paragraph():
    document = normalize_document(
        Document(
            page_count=1,
            blocks=[
                Heading(text="Capitolo 1", level=1),
                Paragraph(text="Testo introduttivo della sezione."),
            ],
        )
    )

    chunks = chunk_document(document, make_config())

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.text == "Documento: Capitolo 1\nContenuto:\nTesto introduttivo della sezione."
    assert chunk.metadata.block_type is BlockType.PARAGRAPH
    assert "Titolo:" not in chunk.text


def test_heading_context_is_propagated_to_following_table():
    document = normalize_document(
        Document(
            page_count=1,
            blocks=[
                Heading(text="Listino", level=1),
                TableBlock(
                    table_id="t1",
                    header=["Modello"],
                    rows=[
                        TableRow(
                            index=0,
                            cells=[TableCell(text="A1", column_index=0, header="Modello")],
                        )
                    ],
                ),
            ],
        )
    )

    chunks = chunk_document(document, make_config())

    assert all(chunk.metadata.block_type is not BlockType.HEADING for chunk in chunks)
    table_chunk = next(chunk for chunk in chunks if chunk.metadata.table_id == "t1")
    assert "Documento: Listino" in table_chunk.text
    assert "Modello: A1" in table_chunk.text


def test_nested_headings_propagate_full_path_to_content():
    document = normalize_document(
        Document(
            page_count=1,
            blocks=[
                Heading(text="Capitolo", level=1),
                Heading(text="Sezione", level=2),
                Paragraph(text="Contenuto della sezione."),
            ],
        )
    )

    chunks = chunk_document(document, make_config())

    assert len(chunks) == 1
    assert "Documento: Capitolo" in chunks[0].text
    assert "Sezione: Sezione" in chunks[0].text
    assert "Contenuto della sezione." in chunks[0].text


def test_orphan_heading_with_parent_section_uses_parent_context():
    document = normalize_document(
        Document(
            page_count=1,
            blocks=[
                Heading(text="Manuale", level=1),
                Heading(text="Ricarica", level=2),
                Heading(text="Codici prodotto", level=2),
            ],
        )
    )

    chunks = chunk_document(document, make_config())

    codici = next(chunk for chunk in chunks if "Codici prodotto" in chunk.text)
    assert codici.text == "Documento: Manuale\nContenuto:\nTitolo: Codici prodotto"
    assert "Ricarica" not in codici.text


def test_consecutive_headings_are_separate_without_duplication():
    document = normalize_document(
        Document(
            page_count=1,
            blocks=[
                Heading(text="Primo", level=1),
                Heading(text="Secondo", level=2),
            ],
        )
    )

    chunks = chunk_document(document, make_config())

    assert len(chunks) == 2
    assert chunks[0].text == "Contenuto:\nTitolo: Primo"
    assert chunks[1].text == "Documento: Primo\nContenuto:\nTitolo: Secondo"
    assert "Secondo Secondo" not in chunks[1].text


def test_heading_title_is_not_duplicated_in_serialization():
    document = normalize_document(
        Document(
            page_count=1,
            blocks=[
                Heading(text="Catalogo prodotti", level=1),
                Heading(text="Accessori", level=2),
                Paragraph(text="Elenco accessori."),
            ],
        )
    )

    chunks = chunk_document(document, make_config())

    for chunk in chunks:
        assert "Accessori Accessori" not in chunk.text
        assert "Catalogo prodotti Catalogo prodotti" not in chunk.text
    content = next(chunk for chunk in chunks if "Elenco accessori." in chunk.text)
    assert "Documento: Catalogo prodotti" in content.text
    assert "Sezione: Accessori" in content.text


def test_headings_without_content_are_not_lost():
    document = normalize_document(
        Document(
            page_count=1,
            blocks=[
                Heading(text="Solo titolo", level=1),
                Heading(text="Altro titolo", level=2),
            ],
        )
    )

    chunks = chunk_document(document, make_config())
    combined = "\n".join(chunk.text for chunk in chunks)

    assert "Solo titolo" in combined
    assert "Altro titolo" in combined
    assert all(chunk.metadata.block_type is BlockType.HEADING for chunk in chunks)


def test_markdown_heading_context_propagates():
    from app.services.rag.parsers import parse_markdown

    document = normalize_document(
        parse_markdown(b"# Documento\n\n## Sezione\n\nContenuto della sezione.\n")
    )

    chunks = chunk_document(document, make_config())

    assert len(chunks) == 1
    assert "Documento: Documento" in chunks[0].text
    assert "Sezione: Sezione" in chunks[0].text
    assert "Contenuto della sezione." in chunks[0].text


def test_docx_heading_context_propagates():
    from app.services.rag.parsers import parse_docx
    from tests.fixtures import make_docx_document

    content = make_docx_document([("heading", "Titolo", 1), ("paragraph", "Testo.")])
    document = normalize_document(parse_docx(content))

    chunks = chunk_document(document, make_config())

    assert len(chunks) == 1
    assert chunks[0].text == "Documento: Titolo\nContenuto:\nTesto."


def test_pdf_heading_context_propagates():
    from app.services.rag.parsers import parse_pdf
    from tests.fixtures import build_pdf

    pdf = build_pdf([("heading", "Titolo Sezione"), ("text", "Testo dopo heading.")])
    document = normalize_document(parse_pdf(pdf))

    chunks = chunk_document(document, make_config())

    assert not any(chunk.metadata.block_type is BlockType.HEADING for chunk in chunks)
    assert any("Testo dopo heading" in chunk.text for chunk in chunks)
    assert any("Documento: Titolo Sezione" in chunk.text for chunk in chunks)


def test_oversized_paragraph_is_split_deterministically():
    text = ". ".join(f"Frase numero {index}" for index in range(60)) + "."
    document = normalize_document(Document(page_count=1, blocks=[Paragraph(text=text)]))

    first = chunk_document(document, make_config(target_size=150, max_size=150, overlap=0))
    second = chunk_document(document, make_config(target_size=150, max_size=150, overlap=0))

    assert len(first) > 1
    assert [chunk.text for chunk in first] == [chunk.text for chunk in second]
    assert all(len(chunk.text) <= 150 + len("Contenuto:\n") for chunk in first)
    assert all(chunk.metadata.oversized for chunk in first)


def test_oversized_table_row_is_kept_intact():
    long_value = "x" * 500
    document = normalize_document(
        Document(
            page_count=1,
            blocks=[
                TableBlock(
                    table_id="t1",
                    header=["Descrizione"],
                    rows=[
                        TableRow(
                            index=0,
                            cells=[
                                TableCell(
                                    text=long_value, column_index=0, header="Descrizione"
                                )
                            ],
                        )
                    ],
                )
            ],
        )
    )

    chunks = chunk_document(document, make_config(target_size=100, max_size=100))

    assert len(chunks) == 1
    assert long_value in chunks[0].text
    assert chunks[0].metadata.oversized is True


def test_list_items_are_atomic_and_grouped():
    document = normalize_document(
        Document(
            page_count=1,
            blocks=[
                ListBlock(
                    items=[ListItem(text=f"Voce {index}", marker="-") for index in range(6)]
                )
            ],
        )
    )

    chunks = chunk_document(document, make_config(target_size=60, max_size=200))

    combined = "\n".join(chunk.text for chunk in chunks)
    for index in range(6):
        assert f"Voce {index}" in combined
    for chunk in chunks:
        assert chunk.text.count("- Voce") >= 1


def test_metadata_can_be_disabled():
    document = make_table_document(2)

    chunks = chunk_document(document, make_config(include_metadata=False))

    assert chunks[0].metadata.page is None
    assert chunks[0].metadata.table_id is None


def test_markdown_table_end_to_end_chunking():
    content = (
        "# Listino\n\n"
        "| Modello | Prezzo |\n| --- | --- |\n"
        "| A1 | 10,00 |\n| B2 | 20,00 |\n| C3 | 30,00 |\n"
    )
    document = normalize_document(parse_markdown(content.encode()))

    chunks = chunk_document(document, make_config(target_size=120, max_size=400))

    combined = "\n".join(chunk.text for chunk in chunks)
    assert "Modello: A1" in combined
    assert "Modello: C3" in combined
    assert "Prezzo: 30,00" in combined
    assert all("Documento: Listino" in chunk.text for chunk in chunks if "Modello:" in chunk.text)
