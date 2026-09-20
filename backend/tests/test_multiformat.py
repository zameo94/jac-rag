import pytest

from app.services.rag.ir import Document, TableBlock
from app.services.rag.normalize import normalize_document
from app.services.rag.parsers import parse_docx, parse_markdown, parse_pdf, parse_text
from tests.fixtures import build_pdf, make_docx_document

HEADER = ["Modello", "Prezzo"]
ROWS = [["A1", "10,00"], ["B2", "20,00"]]


def _markdown_bytes() -> bytes:
    return (
        "# Capitolo 1\n\n"
        "| Modello | Prezzo |\n| --- | --- |\n"
        "| A1 | 10,00 |\n| B2 | 20,00 |\n"
    ).encode()


def _docx_bytes() -> bytes:
    return make_docx_document(
        [
            ("heading", "Capitolo 1", 1),
            ("table", HEADER, ROWS),
        ]
    )


def _pdf_bytes() -> bytes:
    return build_pdf(
        [
            ("heading", "Capitolo 1"),
            ("table", HEADER, ROWS, True),
        ]
    )


def _txt_bytes() -> bytes:
    return "Capitolo 1\n\nModello: A1 Prezzo: 10,00\nModello: B2 Prezzo: 20,00\n".encode()


@pytest.mark.parametrize(
    "parser,content",
    [
        (parse_markdown, _markdown_bytes()),
        (parse_docx, _docx_bytes()),
        (parse_pdf, _pdf_bytes()),
        (parse_text, _txt_bytes()),
    ],
)
def test_every_format_preserves_values(parser, content):
    document = normalize_document(parser(content))

    assert isinstance(document, Document)
    text = document.text
    for expected in ["A1", "10,00", "B2", "20,00"]:
        assert expected in text


@pytest.mark.parametrize(
    "parser,content",
    [
        (parse_markdown, _markdown_bytes()),
        (parse_docx, _docx_bytes()),
        (parse_pdf, _pdf_bytes()),
    ],
)
def test_structured_formats_reconstruct_table(parser, content):
    document = normalize_document(parser(content))

    tables = [block for block in document.blocks if isinstance(block, TableBlock)]
    assert len(tables) == 1
    table = tables[0]
    assert table.header == HEADER
    assert [row.cell_map() for row in table.rows] == [
        {"Modello": "A1", "Prezzo": "10,00"},
        {"Modello": "B2", "Prezzo": "20,00"},
    ]


def test_txt_does_not_invent_tables():
    document = normalize_document(parse_text(_txt_bytes()))

    assert not any(isinstance(block, TableBlock) for block in document.blocks)
