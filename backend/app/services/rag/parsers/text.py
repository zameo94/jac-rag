from __future__ import annotations

from app.services.rag.diagnostics import ExtractionDiagnostics
from app.services.rag.ir import BlockLike, Document, Paragraph
from app.services.rag.parsers.base import DocumentParser


class TxtParser(DocumentParser):
    """Conservative: TXT carries no reliable structure, so we only split on
    blank lines into paragraphs. No headings, lists or tables are invented."""

    mime_types = ("text/plain",)

    def parse(self, content: bytes, *, source: str | None = None) -> Document:
        text = content.decode("utf-8", errors="replace")
        diagnostics = ExtractionDiagnostics(pages=1)
        blocks: list[BlockLike] = []

        for block_text in _paragraphs(text):
            blocks.append(Paragraph(text=block_text))
            diagnostics.text_blocks += 1

        return Document(source=source, page_count=1, blocks=blocks, diagnostics=diagnostics)


def _paragraphs(text: str) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append("\n".join(current))
            current = []
    if current:
        paragraphs.append("\n".join(current))
    return paragraphs
