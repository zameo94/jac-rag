from app.services.rag.parsers.base import ParsedDocument


def parse_text(content: bytes) -> ParsedDocument:
    text = content.decode("utf-8", errors="replace").strip()
    return ParsedDocument(text=text, page_count=1)
