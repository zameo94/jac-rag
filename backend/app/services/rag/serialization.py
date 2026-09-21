"""Semantic serialization: turn IR blocks into readable, self-descriptive text.

The goal is that a single table row, retrieved in isolation, is understandable
by both an embedding model and an LLM. Labels come from the real table headers;
nothing is hardcoded per domain.
"""

from __future__ import annotations

from app.services.rag.ir import (
    BlockLike,
    CodeBlock,
    Document,
    FieldBlock,
    FigureBlock,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    QuoteBlock,
    TableBlock,
    TableRow,
)

CONTEXT_PREFIX = {
    "document": "Documento",
    "section": "Sezione",
    "table": "Tabella",
    "columns": "Colonne",
}


def _label_for_row(row: TableRow, table: TableBlock) -> dict[str, str]:
    labelled: dict[str, str] = {}
    for cell in row.cells:
        header = cell.header
        if not header and 0 <= cell.column_index < len(table.header):
            header = table.header[cell.column_index]
        key = header or f"col_{cell.column_index + 1}"
        labelled[key] = cell.text
    return labelled


def serialize_table_row(table: TableBlock, row: TableRow) -> str:
    """One row as ``Header: value`` lines. Falls back to positional join."""
    values = _label_for_row(row, table)
    if table.header:
        lines = [
            f"{header}: {values.get(header, '')}".rstrip()
            for header in table.header
            if values.get(header, "").strip()
        ]
        if lines:
            return "\n".join(lines)
    cells = [cell.text for cell in row.cells if cell.text.strip()]
    return " | ".join(cells)


def table_context_lines(table: TableBlock, *, section_path: tuple[str, ...] = ()) -> list[str]:
    lines: list[str] = []
    if section_path:
        lines.append(f"{CONTEXT_PREFIX['section']}: {' > '.join(section_path)}")
    if table.caption:
        lines.append(f"{CONTEXT_PREFIX['table']}: {table.caption}")
    if table.header:
        lines.append(f"{CONTEXT_PREFIX['columns']}: {', '.join(h for h in table.header if h)}")
    return lines


def serialize_table(table: TableBlock) -> str:
    parts: list[str] = []
    if table.caption:
        parts.append(table.caption)
    rows = [serialize_table_row(table, row) for row in table.rows if not row.is_empty]
    parts.extend(row for row in rows if row)
    return "\n".join(parts)


def serialize_block(block: BlockLike) -> str:
    if isinstance(block, Heading):
        return block.text.strip()
    if isinstance(block, Paragraph):
        return block.text.strip()
    if isinstance(block, ListBlock):
        return "\n".join(
            f"{item.marker} {item.text}".strip() for item in block.items if item.text.strip()
        )
    if isinstance(block, ListItem):
        return f"{block.marker} {block.text}".strip()
    if isinstance(block, TableBlock):
        return serialize_table(block)
    if isinstance(block, FieldBlock):
        return "\n".join(
            f"{item.label}: {item.value}"
            for item in block.fields
            if item.label and item.value
        )
    if isinstance(block, FigureBlock):
        return block.caption.strip()
    if isinstance(block, CodeBlock):
        return block.text.strip()
    if isinstance(block, QuoteBlock):
        return block.text.strip()
    return getattr(block, "text", "").strip()


def serialize_document(document: Document) -> str:
    parts = [serialize_block(block) for block in document.blocks]
    return "\n\n".join(part for part in parts if part)
