from io import BytesIO

from pypdf import PdfReader

from app.services.rag.parsers.base import ParsedDocument


def parse_pdf(content: bytes) -> ParsedDocument:
    reader = PdfReader(BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    return ParsedDocument(text=text, page_count=len(reader.pages))
