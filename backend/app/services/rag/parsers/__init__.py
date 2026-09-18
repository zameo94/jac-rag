from collections.abc import Callable

from app.services.rag.parsers.base import ParsedDocument
from app.services.rag.parsers.docx import parse_docx
from app.services.rag.parsers.pdf import parse_pdf
from app.services.rag.parsers.text import parse_text

Parser = Callable[[bytes], ParsedDocument]

PARSERS: dict[str, Parser] = {
    "application/pdf": parse_pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": parse_docx,
    "application/msword": parse_docx,
    "text/plain": parse_text,
    "text/markdown": parse_text,
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


def get_parser(mime: str) -> Parser:
    try:
        return PARSERS[mime]
    except KeyError as exc:
        raise ValueError(f"No parser registered for mime type: {mime}") from exc
