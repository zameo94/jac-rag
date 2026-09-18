import pytest

from app.services.rag.parsers import (
    SUPPORTED_EXTENSIONS,
    SUPPORTED_MIME_TYPES,
    get_parser,
    resolve_mime,
)
from app.services.rag.parsers.base import ParsedDocument
from app.services.rag.parsers.docx import parse_docx
from app.services.rag.parsers.pdf import parse_pdf
from app.services.rag.parsers.text import parse_text
from tests.fixtures import make_docx, make_pdf


def test_parse_text_decodes_utf8():
    parsed = parse_text("Ciao mondo\nseconda riga".encode("utf-8"))

    assert parsed.text == "Ciao mondo\nseconda riga"
    assert parsed.page_count == 1


def test_parse_text_replaces_invalid_bytes():
    parsed = parse_text(b"valid \xff\xfe bytes")

    assert "valid" in parsed.text


def test_parse_text_strips_whitespace():
    parsed = parse_text(b"   \n\n  hello  \n\n  ")

    assert parsed.text == "hello"


def test_parse_docx_extracts_paragraphs():
    parsed = parse_docx(make_docx(["Primo paragrafo", "Secondo paragrafo"]))

    assert "Primo paragrafo" in parsed.text
    assert "Secondo paragrafo" in parsed.text
    assert parsed.page_count == 1


def test_parse_pdf_extracts_text_layer():
    parsed = parse_pdf(make_pdf("Contenuto del PDF"))

    assert "Contenuto del PDF" in parsed.text
    assert parsed.page_count == 1


def test_has_text_layer_true_for_text_document():
    parsed = ParsedDocument(text="a" * 100, page_count=1)

    assert parsed.has_text_layer() is True


def test_has_text_layer_false_for_scanned_document():
    parsed = ParsedDocument(text="", page_count=5)

    assert parsed.has_text_layer() is False


def test_has_text_layer_uses_page_count():
    parsed = ParsedDocument(text="x" * 100, page_count=10)

    assert parsed.chars_per_page == 10
    assert parsed.has_text_layer() is False


def test_chars_per_page_without_pages():
    parsed = ParsedDocument(text="abc", page_count=0)

    assert parsed.chars_per_page == 3


def test_resolve_mime_prefers_valid_provided_mime():
    assert resolve_mime("weird.bin", "application/pdf") == "application/pdf"


def test_resolve_mime_falls_back_to_extension():
    assert resolve_mime("report.PDF", "application/octet-stream") == "application/pdf"
    assert resolve_mime("notes.md", None) == "text/markdown"
    assert resolve_mime("notes.txt", None) == "text/plain"


def test_resolve_mime_returns_none_for_unknown():
    assert resolve_mime("malware.exe", "application/octet-stream") is None


def test_resolve_mime_returns_none_for_unknown_without_extension():
    assert resolve_mime("noextension", None) is None


def test_get_parser_returns_callable_for_supported_mime():
    for mime in SUPPORTED_MIME_TYPES:
        assert callable(get_parser(mime))


def test_get_parser_raises_for_unknown_mime():
    with pytest.raises(ValueError):
        get_parser("application/unknown")


def test_supported_extensions_are_lowercase():
    assert all(extension.startswith(".") for extension in SUPPORTED_EXTENSIONS)
    assert all(extension == extension.lower() for extension in SUPPORTED_EXTENSIONS)
