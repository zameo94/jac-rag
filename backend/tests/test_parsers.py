import pytest

from app.services.rag.ir import (
    Document,
    FieldBlock,
    Heading,
    ListBlock,
    Paragraph,
    TableBlock,
)
from app.services.rag.parsers import (
    SUPPORTED_EXTENSIONS,
    SUPPORTED_MIME_TYPES,
    get_parser,
    parse_docx,
    parse_markdown,
    parse_pdf,
    parse_text,
    resolve_mime,
)
from app.services.rag.parsers.base import DocumentParser
from tests.fixtures import build_pdf, make_docx_document, make_markdown, make_pdf, make_positioned_pdf

# --------------------------------------------------------------------------- #
# Registry                                                                     #
# --------------------------------------------------------------------------- #


def test_resolve_mime_prefers_valid_provided_mime():
    assert resolve_mime("weird.bin", "application/pdf") == "application/pdf"


def test_resolve_mime_falls_back_to_extension():
    assert resolve_mime("report.PDF", "application/octet-stream") == "application/pdf"
    assert resolve_mime("notes.md", None) == "text/markdown"
    assert resolve_mime("notes.txt", None) == "text/plain"


def test_resolve_mime_returns_none_for_unknown():
    assert resolve_mime("malware.exe", "application/octet-stream") is None
    assert resolve_mime("noextension", None) is None


def test_get_parser_returns_document_parser():
    for mime in SUPPORTED_MIME_TYPES:
        assert isinstance(get_parser(mime), DocumentParser)


def test_get_parser_raises_for_unknown_mime():
    with pytest.raises(ValueError):
        get_parser("application/unknown")


def test_supported_extensions_are_lowercase():
    assert all(extension.startswith(".") for extension in SUPPORTED_EXTENSIONS)
    assert all(extension == extension.lower() for extension in SUPPORTED_EXTENSIONS)


def test_markdown_is_supported():
    assert "text/markdown" in SUPPORTED_MIME_TYPES


# --------------------------------------------------------------------------- #
# TXT                                                                          #
# --------------------------------------------------------------------------- #


def test_parse_text_creates_paragraphs_only():
    document = parse_text(b"Primo paragrafo\nsu due righe.\n\nSecondo paragrafo.")

    assert isinstance(document, Document)
    assert all(isinstance(block, Paragraph) for block in document.blocks)
    assert len(document.blocks) == 2
    assert document.blocks[0].text == "Primo paragrafo\nsu due righe."
    assert "Secondo paragrafo." in document.text


def test_parse_text_replaces_invalid_bytes():
    document = parse_text(b"valid \xff\xfe bytes")

    assert "valid" in document.text


def test_parse_text_does_not_invent_structure():
    document = parse_text(b"# Not a heading\n- not a list\n| not | a table |")

    assert all(isinstance(block, Paragraph) for block in document.blocks)
    assert not any(isinstance(block, Heading) for block in document.blocks)
    assert not any(isinstance(block, TableBlock) for block in document.blocks)


# --------------------------------------------------------------------------- #
# Markdown                                                                     #
# --------------------------------------------------------------------------- #


def test_parse_markdown_builds_sections_and_prose():
    content = "# Titolo\n\n## Sezione\n\nTesto della sezione.\n"
    document = parse_markdown(make_markdown(content))

    kinds = [type(block).__name__ for block in document.blocks]
    assert kinds == ["Heading", "Heading", "Paragraph"]
    assert document.blocks[0].level == 1
    assert document.blocks[1].level == 2


def test_parse_markdown_builds_lists():
    document = parse_markdown(make_markdown("- uno\n- due\n\n1. primo\n2. secondo\n"))

    lists = [block for block in document.blocks if isinstance(block, ListBlock)]
    assert len(lists) == 2
    assert [item.text for item in lists[0].items] == ["uno", "due"]
    assert lists[1].ordered is True


def test_parse_markdown_builds_table_with_header():
    content = "| Modello | Prezzo |\n| --- | --- |\n| A1 | 10,00 |\n| B2 | 20,00 |\n"
    document = parse_markdown(make_markdown(content))

    tables = [block for block in document.blocks if isinstance(block, TableBlock)]
    assert len(tables) == 1
    table = tables[0]
    assert table.header == ["Modello", "Prezzo"]
    assert [row.cell_map() for row in table.rows] == [
        {"Modello": "A1", "Prezzo": "10,00"},
        {"Modello": "B2", "Prezzo": "20,00"},
    ]
    assert "Modello: A1" in document.text
    assert "Prezzo: 10,00" in document.text


def test_parse_markdown_keeps_code_and_quotes():
    content = "> citazione\n\n```python\nprint(1)\n```\n"
    document = parse_markdown(make_markdown(content))

    kinds = [type(block).__name__ for block in document.blocks]
    assert kinds == ["QuoteBlock", "CodeBlock"]


# --------------------------------------------------------------------------- #
# DOCX                                                                         #
# --------------------------------------------------------------------------- #


def test_parse_docx_preserves_document_order():
    blocks = [
        ("heading", "Capitolo 1", 1),
        ("paragraph", "Introduzione."),
        ("table", ["A", "B"], [["1", "2"], ["3", "4"]]),
        ("paragraph", "Conclusione."),
    ]
    document = parse_docx(make_docx_document(blocks))

    kinds = [type(block).__name__ for block in document.blocks]
    assert kinds == ["Heading", "Paragraph", "TableBlock", "Paragraph"]


def test_parse_docx_table_headers_and_cells():
    blocks = [("table", ["Modello", "Prezzo"], [["A1", "10,00"], ["B2", "20,00"]])]
    document = parse_docx(make_docx_document(blocks))

    table = next(block for block in document.blocks if isinstance(block, TableBlock))
    assert table.header == ["Modello", "Prezzo"]
    assert table.rows[1].cell_map() == {"Modello": "B2", "Prezzo": "20,00"}


def test_parse_docx_lists():
    blocks = [("list", ["uno", "due", "tre"])]
    document = parse_docx(make_docx_document(blocks))

    lists = [block for block in document.blocks if isinstance(block, ListBlock)]
    assert len(lists) == 1
    assert [item.text for item in lists[0].items] == ["uno", "due", "tre"]


# --------------------------------------------------------------------------- #
# PDF                                                                          #
# --------------------------------------------------------------------------- #


def test_parse_pdf_extracts_text_layer():
    document = parse_pdf(make_pdf("Contenuto del PDF"))

    assert isinstance(document, Document)
    assert "Contenuto del PDF" in document.text
    assert document.page_count == 1


def test_parse_pdf_reconstructs_table_with_header():
    pdf = build_pdf(
        [
            ("heading", "Listino"),
            ("table", ["Modello", "Prezzo"], [["A1", "10,00"], ["B2", "20,00"]], True),
        ]
    )
    document = parse_pdf(pdf)

    tables = [block for block in document.blocks if isinstance(block, TableBlock)]
    assert len(tables) == 1
    table = tables[0]
    assert table.header == ["Modello", "Prezzo"]
    assert table.rows[0].cell_map() == {"Modello": "A1", "Prezzo": "10,00"}
    assert "Modello: B2" in document.text
    assert table.page == 1


def test_parse_pdf_detects_heading():
    pdf = build_pdf([("heading", "Capitolo Primo"), ("text", "Paragrafo di prova.")])
    document = parse_pdf(pdf)

    assert any(isinstance(block, Heading) for block in document.blocks)


def test_parse_pdf_preserves_text_around_table():
    pdf = build_pdf(
        [
            ("text", "Testo prima della tabella."),
            ("table", ["Colonna"], [["valore"]], True),
            ("text", "Testo dopo la tabella."),
        ]
    )
    document = parse_pdf(pdf)

    assert "Testo prima della tabella." in document.text
    assert "Testo dopo la tabella." in document.text


def test_parse_pdf_multiline_and_empty_cells():
    pdf = build_pdf(
        [
            (
                "table",
                ["Descrizione", "Note"],
                [["Prima riga\nseconda riga", ""], ["Solo testo", "ok"]],
                True,
            )
        ]
    )
    document = parse_pdf(pdf)

    table = next(block for block in document.blocks if isinstance(block, TableBlock))
    assert len(table.rows) == 2
    first = table.rows[0].cell_map()
    assert "Prima riga" in first["Descrizione"]
    assert first["Note"] == ""
    assert table.rows[1].cell_map()["Note"] == "ok"


def test_parse_pdf_table_values_are_not_swapped_between_rows():
    rows = [[f"P{i}", str(i * 10)] for i in range(1, 6)]
    pdf = build_pdf([("table", ["Nome", "Valore"], rows, True)])
    document = parse_pdf(pdf)

    table = next(block for block in document.blocks if isinstance(block, TableBlock))
    for index, row in enumerate(table.rows, start=1):
        mapping = row.cell_map()
        assert mapping["Nome"] == f"P{index}"
        assert mapping["Valore"] == str(index * 10)


def test_parse_pdf_multi_page_table_marks_continuation():
    rows = [[f"Riga {index}", str(index)] for index in range(1, 60)]
    pdf = build_pdf([("table", ["Nome", "Valore"], rows, True)])
    document = parse_pdf(pdf)

    tables = [block for block in document.blocks if isinstance(block, TableBlock)]
    assert document.page_count >= 2
    assert tables, "expected at least one reconstructed table"
    total_rows = sum(len(table.rows) for table in tables)
    assert total_rows == len(rows)


def test_parse_pdf_marks_repeated_header_footer():
    pdf = build_pdf(
        [
            ("text", "Pagina uno."),
            ("pagebreak",),
            ("text", "Pagina due."),
            ("pagebreak",),
            ("text", "Pagina tre."),
        ],
        header="Documento Riservato",
        footer="Uso interno",
    )
    document = parse_pdf(pdf)

    repeated = [block for block in document.blocks if block.repeated_layout]
    texts = {block.text for block in repeated if isinstance(block, Paragraph)}
    assert "Documento Riservato" in texts


def test_parse_pdf_multi_column_does_not_lose_content():
    pdf = build_pdf(
        [
            (
                "table",
                None,
                [
                    ["Testo colonna sinistra con parole.", "Testo colonna destra con parole."],
                    ["Altra riga sinistra.", "Altra riga destra."],
                ],
                False,
            )
        ]
    )
    document = parse_pdf(pdf)

    assert "colonna sinistra" in document.text
    assert "colonna destra" in document.text


def test_parse_pdf_empty_file_has_no_text_layer():
    document = parse_pdf(make_pdf(""))

    assert document.has_text_layer() is False


def test_parse_pdf_preserves_label_value_relation():
    pdf = make_positioned_pdf([(72, 700, "Netto in busta"), (300, 700, "1.821,00")])

    document = parse_pdf(pdf)

    assert "Netto in busta: 1.821,00" in document.text
    assert any(isinstance(block, Paragraph) for block in document.blocks)


def test_parse_pdf_does_not_pair_two_values():
    pdf = make_positioned_pdf([(72, 700, "2.500,00"), (300, 700, "1.821,00")])

    document = parse_pdf(pdf)

    assert "2.500,00" in document.text
    assert "1.821,00" in document.text
    assert ": 1.821,00" not in document.text


def test_parse_pdf_links_column_header_to_value():
    pdf = make_positioned_pdf(
        [
            (72, 740, "LORDO"),
            (300, 740, "NETTO IN BUSTA"),
            (72, 700, "2.500,00"),
            (300, 700, "1.821,00"),
        ]
    )

    document = parse_pdf(pdf)

    assert "NETTO IN BUSTA: 1.821,00" in document.text
    assert "LORDO: 2.500,00" in document.text


def test_parse_pdf_emits_fields_block():
    pdf = make_positioned_pdf(
        [
            (72, 740, "LORDO"),
            (300, 740, "NETTO IN BUSTA"),
            (72, 700, "2.500,00"),
            (300, 700, "1.828,00"),
        ]
    )

    document = parse_pdf(pdf)

    field_blocks = [block for block in document.blocks if isinstance(block, FieldBlock)]
    assert field_blocks, "expected a fields block"
    pairs = [
        (item.label, item.value) for block in field_blocks for item in block.fields
    ]
    assert ("NETTO IN BUSTA", "1.828,00") in pairs
