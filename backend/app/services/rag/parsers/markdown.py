from __future__ import annotations

import re

from app.services.rag.diagnostics import ExtractionDiagnostics
from app.services.rag.ir import (
    BlockLike,
    CodeBlock,
    Document,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    QuoteBlock,
    TableBlock,
    TableCell,
    TableRow,
)
from app.services.rag.parsers.base import DocumentParser

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
LIST_RE = re.compile(r"^(?P<marker>[-*+]|\d+[.)])\s+(?P<text>.+)$")
QUOTE_RE = re.compile(r"^>\s?(?P<text>.*)$")
FENCE_RE = re.compile(r"^```(?P<lang>[\w+-]*)\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)+\|?\s*$")


def _split_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [" ".join(cell.split()) for cell in stripped.split("|")]


def _is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    return "|" in lines[index] and bool(TABLE_SEPARATOR_RE.match(lines[index + 1]))


class MarkdownParser(DocumentParser):
    mime_types = ("text/markdown",)

    def parse(self, content: bytes, *, source: str | None = None) -> Document:
        text = content.decode("utf-8", errors="replace")
        lines = text.splitlines()
        diagnostics = ExtractionDiagnostics(pages=1)
        blocks: list[BlockLike] = []
        sequence = 0
        paragraph: list[str] = []
        list_open = False

        def flush_paragraph() -> None:
            nonlocal paragraph
            if paragraph:
                joined = "\n".join(paragraph).strip()
                if joined:
                    blocks.append(Paragraph(text=joined))
                    diagnostics.text_blocks += 1
                paragraph = []

        index = 0
        while index < len(lines):
            line = lines[index]

            if FENCE_RE.match(line):
                flush_paragraph()
                list_open = False
                language = FENCE_RE.match(line).group("lang") or None
                index += 1
                code_lines: list[str] = []
                while index < len(lines) and not FENCE_RE.match(lines[index]):
                    code_lines.append(lines[index])
                    index += 1
                blocks.append(CodeBlock(text="\n".join(code_lines), language=language))
                diagnostics.fallback_blocks += 1
                index += 1
                continue

            heading = HEADING_RE.match(line)
            if heading:
                flush_paragraph()
                list_open = False
                blocks.append(Heading(text=heading.group(2), level=len(heading.group(1))))
                diagnostics.headings += 1
                index += 1
                continue

            if _is_table_start(lines, index):
                flush_paragraph()
                list_open = False
                sequence += 1
                header_cells = _split_row(lines[index])
                index += 2
                rows: list[TableRow] = []
                row_index = 0
                while index < len(lines) and "|" in lines[index] and lines[index].strip():
                    cells = [
                        TableCell(
                            text=value,
                            column_index=column_index,
                            header=header_cells[column_index]
                            if column_index < len(header_cells)
                            else None,
                        )
                        for column_index, value in enumerate(_split_row(lines[index]))
                    ]
                    rows.append(TableRow(index=row_index, cells=cells))
                    row_index += 1
                    index += 1
                blocks.append(TableBlock(table_id=f"table{sequence}", header=header_cells, rows=rows))
                diagnostics.tables_detected += 1
                diagnostics.rows_detected += len(rows)
                diagnostics.cells_detected += sum(len(row.cells) for row in rows)
                continue

            list_match = LIST_RE.match(line)
            if list_match:
                flush_paragraph()
                marker = list_match.group("marker")
                item = ListItem(
                    text=list_match.group("text").strip(),
                    marker=marker,
                    ordered=marker[:1].isdigit(),
                )
                if (
                    list_open
                    and blocks
                    and isinstance(blocks[-1], ListBlock)
                    and blocks[-1].ordered == item.ordered
                ):
                    blocks[-1].items.append(item)
                else:
                    blocks.append(ListBlock(items=[item], ordered=item.ordered))
                list_open = True
                diagnostics.list_items += 1
                index += 1
                continue

            quote_match = QUOTE_RE.match(line)
            if quote_match:
                flush_paragraph()
                list_open = False
                blocks.append(QuoteBlock(text=quote_match.group("text").strip()))
                diagnostics.fallback_blocks += 1
                index += 1
                continue

            if not line.strip():
                flush_paragraph()
                list_open = False
                index += 1
                continue

            paragraph.append(line)
            list_open = False
            index += 1

        flush_paragraph()

        return Document(source=source, page_count=1, blocks=blocks, diagnostics=diagnostics)
