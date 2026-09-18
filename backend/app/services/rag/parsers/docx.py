from io import BytesIO

from docx import Document as DocxDocument

from app.services.rag.parsers.base import ParsedDocument


def parse_docx(content: bytes) -> ParsedDocument:
    document = DocxDocument(BytesIO(content))
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    text = "\n".join(paragraphs).strip()
    return ParsedDocument(text=text, page_count=1)
