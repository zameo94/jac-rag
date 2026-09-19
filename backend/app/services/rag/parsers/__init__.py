from __future__ import annotations

from app.services.rag.ir import Document
from app.services.rag.parsers.base import DocumentParser
from app.services.rag.parsers.docx import DocxParser
from app.services.rag.parsers.markdown import MarkdownParser
from app.services.rag.parsers.pdf import PdfParser
from app.services.rag.parsers.text import TxtParser

_PDF = PdfParser()
_DOCX = DocxParser()
_MARKDOWN = MarkdownParser()
_TXT = TxtParser()

PARSERS: dict[str, DocumentParser] = {
    mime: parser
    for parser in (_PDF, _DOCX, _MARKDOWN, _TXT)
    for mime in parser.mime_types
}

EXTENSION_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".txt": "text/plain",
    ".md": "text/markdown",
}

SUPPORTED_MIME_TYPES = frozenset(PARSERS.keys())
SUPPORTED_EXTENSIONS = frozenset(EXTENSION_MIME.keys())


def resolve_mime(filename: str, provided_mime: str | None = None) -> str | None:
    if provided_mime in PARSERS:
        return provided_mime
    lowered = filename.lower()
    for extension, mime in EXTENSION_MIME.items():
        if lowered.endswith(extension):
            return mime
    return None


def get_parser(mime: str) -> DocumentParser:
    try:
        return PARSERS[mime]
    except KeyError as exc:
        raise ValueError(f"No parser registered for mime type: {mime}") from exc


def parse_pdf(content: bytes, *, source: str | None = None) -> Document:
    return _PDF.parse(content, source=source)


def parse_docx(content: bytes, *, source: str | None = None) -> Document:
    return _DOCX.parse(content, source=source)


def parse_markdown(content: bytes, *, source: str | None = None) -> Document:
    return _MARKDOWN.parse(content, source=source)


def parse_text(content: bytes, *, source: str | None = None) -> Document:
    return _TXT.parse(content, source=source)
