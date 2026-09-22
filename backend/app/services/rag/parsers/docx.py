from __future__ import annotations

import logging
import re
from collections.abc import Iterator, Sequence
from io import BytesIO

from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph

from app.services.rag.diagnostics import ExtractionDiagnostics
from app.services.rag.ir import (
    BlockLike,
    Document,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    TableBlock,
    TableCell,
    TableRow,
)
from app.services.rag.parsers.base import DocumentParser

HEADING_STYLE_RE = re.compile(r"heading\s*(\d+)", re.IGNORECASE)
LIST_STYLE_RE = re.compile(r"list", re.IGNORECASE)

logger = logging.getLogger(__name__)


def _iter_block_items(document: DocxDocument) -> Iterator[DocxParagraph | DocxTable]:
    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield DocxParagraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield DocxTable(child, document)


def _heading_level(paragraph: DocxParagraph) -> int | None:
    style = paragraph.style.name if paragraph.style is not None else ""
    match = HEADING_STYLE_RE.search(style)
    if match:
        return int(match.group(1))
    return None


def _is_list_item(paragraph: DocxParagraph) -> bool:
    style = paragraph.style.name if paragraph.style is not None else ""
    if LIST_STYLE_RE.search(style):
        return True
    properties = paragraph._p.pPr
    return bool(properties is not None and properties.numPr is not None)


def _table_block(table: DocxTable, sequence: int) -> TableBlock:
    raw_rows: list[list[str]] = []
    for row in table.rows:
        raw_rows.append([cell.text for cell in row.cells])

    header = []
    if raw_rows:
        first = [" ".join(cell.split()) for cell in raw_rows[0]]
        if all(first):
            header = first
    data_rows = raw_rows[1:] if header else raw_rows

    rows: list[TableRow] = []
    for row_index, raw in enumerate(data_rows):
        cells = [
            TableCell(
                text=" ".join(value.split()),
                column_index=column_index,
                header=header[column_index] if column_index < len(header) else None,
            )
            for column_index, value in enumerate(raw)
        ]
        rows.append(TableRow(index=row_index, cells=cells))

    widths = {len(row) for row in raw_rows}
    return TableBlock(
        table_id=f"table{sequence}",
        header=header,
        rows=rows,
        suspicious=len(widths) > 1,
    )


class DocxParser(DocumentParser):
    mime_types = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    def parse(
        self,
        content: bytes,
        *,
        source: str | None = None,
        languages: Sequence[str] | None = None,
    ) -> Document:
        document = DocxDocument(BytesIO(content))
        diagnostics = ExtractionDiagnostics(pages=1)
        blocks: list[BlockLike] = []
        sequence = 0

        for item in _iter_block_items(document):
            try:
                if isinstance(item, DocxParagraph):
                    text = item.text.strip()
                    if not text:
                        continue
                    level = _heading_level(item)
                    if level is not None:
                        blocks.append(Heading(text=text, level=level))
                        diagnostics.headings += 1
                    elif _is_list_item(item):
                        number_prefix = ""
                        if item._p.pPr is not None and item._p.pPr.numPr is not None:
                            number_prefix = "-"
                        item_block = ListItem(text=text, marker=number_prefix, ordered=False)
                        if blocks and isinstance(blocks[-1], ListBlock):
                            blocks[-1].items.append(item_block)
                        else:
                            blocks.append(ListBlock(items=[item_block]))
                        diagnostics.list_items += 1
                    else:
                        blocks.append(Paragraph(text=text))
                        diagnostics.text_blocks += 1
                else:
                    sequence += 1
                    block = _table_block(item, sequence)
                    diagnostics.tables_detected += 1
                    diagnostics.rows_detected += len(block.rows)
                    diagnostics.cells_detected += sum(len(row.cells) for row in block.rows)
                    if block.suspicious:
                        diagnostics.suspicious_tables += 1
                    blocks.append(block)
            except Exception as exc:
                diagnostics.add_warning(f"docx block skipped: {exc}")
                logger.warning("docx block skipped: %s", exc)

        return Document(
            source=source, page_count=1, blocks=blocks, diagnostics=diagnostics
        )
