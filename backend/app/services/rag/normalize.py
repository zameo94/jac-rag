"""Normalization applied to every Document IR regardless of source format.

Responsibilities:
- assign deterministic ordering;
- assign stable ``source_block_id`` values;
- propagate the section path (from headings) to following blocks;
- roll document-level diagnostics up to date.

It never invents structure: it only propagates what the parser already provided.
"""

from __future__ import annotations

from app.services.rag.diagnostics import ExtractionDiagnostics
from app.services.rag.ir import (
    BlockLike,
    CodeBlock,
    Document,
    FigureBlock,
    GenericBlock,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    QuoteBlock,
    TableBlock,
)


def normalize_document(document: Document) -> Document:
    ordered: list[BlockLike] = []
    section_stack: list[str] = []
    diagnostics = ExtractionDiagnostics(pages=document.page_count)

    for index, block in enumerate(document.blocks):
        block.order = index
        if block.source_block_id is None:
            block.source_block_id = f"block-{index}"

        if isinstance(block, Heading):
            if block.section_path:
                section_stack = list(block.section_path)
            level = max(1, block.level)
            parent_path = section_stack[: level - 1]
            block.section_path = tuple(parent_path)
            section_stack = parent_path + [block.text]
            diagnostics.headings += 1
        else:
            if not block.section_path:
                block.section_path = tuple(section_stack)

        ordered.append(block)
        _count(diagnostics, block)

    document.blocks = ordered
    document.diagnostics = diagnostics
    return document


def _count(diagnostics: ExtractionDiagnostics, block: BlockLike) -> None:
    if isinstance(block, Paragraph):
        diagnostics.text_blocks += 1
    elif isinstance(block, ListBlock):
        diagnostics.list_items += len(block.items)
        for position, item in enumerate(block.items):
            item.order = position
            if item.source_block_id is None:
                item.source_block_id = f"{block.source_block_id}-item-{position}"
    elif isinstance(block, ListItem):
        diagnostics.list_items += 1
    elif isinstance(block, TableBlock):
        diagnostics.tables_detected += 1
        diagnostics.rows_detected += len(block.rows)
        diagnostics.cells_detected += sum(len(row.cells) for row in block.rows)
        if block.suspicious:
            diagnostics.suspicious_tables += 1
    elif isinstance(block, FigureBlock):
        diagnostics.figures += 1
    elif isinstance(block, CodeBlock | QuoteBlock | GenericBlock):
        diagnostics.fallback_blocks += 1
