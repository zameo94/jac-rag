from __future__ import annotations

import logging
import math
import re
import statistics
from io import BytesIO
from typing import Any

import pdfplumber

from app.services.rag.diagnostics import ExtractionDiagnostics
from app.services.rag.ir import (
    BlockLike,
    BoundingBox,
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

logger = logging.getLogger(__name__)

LIST_RE = re.compile(r"^(?P<marker>(?:\d+[.)])|[-•*·–])\s+")
NUMBERISH_RE = re.compile(r"^[\d\s.,%€$+\-()]+$")
MULTILEVEL_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)+)[.)]?\s+\S")
SIMPLE_HEADING_RE = re.compile(r"^\d+[.)]\s+[A-ZÀ-ÖØ-Ý][^.!?]{0,70}$")

HEADING_SIZE_RATIO = 1.15
PARAGRAPH_GAP_RATIO = 1.6
HEADER_FOOTER_ZONE = 0.12
REPEATED_PAGE_RATIO = 0.6
CONTINUATION_TOP_RATIO = 0.25
MIN_TABLE_ROWS = 2
MIN_TABLE_COLS = 2


def _bbox(box: tuple[float, float, float, float]) -> BoundingBox:
    return BoundingBox(x0=box[0], top=box[1], x1=box[2], bottom=box[3])


def _in_any_bbox(boxes: list[tuple[float, float, float, float]], obj: dict[str, Any]) -> bool:
    x0, top, x1, bottom = obj["x0"], obj["top"], obj["x1"], obj["bottom"]
    for bx0, btop, bx1, bbottom in boxes:
        if x0 >= bx0 - 1 and x1 <= bx1 + 1 and top >= btop - 1 and bottom <= bbottom + 1:
            return True
    return False


def _line_size(line: dict[str, Any]) -> float:
    sizes = [char.get("size") or 0 for char in line.get("chars", [])]
    return max(sizes) if sizes else 0.0


def _body_size(lines: list[dict[str, Any]]) -> float:
    sizes = [_line_size(line) for line in lines if _line_size(line) > 0]
    return statistics.median(sizes) if sizes else 12.0


def _heading_level(text: str, size: float, body: float) -> int:
    match = MULTILEVEL_HEADING_RE.match(text)
    if match:
        return min(6, match.group(1).count(".") + 1)
    if SIMPLE_HEADING_RE.match(text):
        return 1
    ratio = size / body if body else 1.0
    if ratio >= 1.6:
        return 1
    if ratio >= 1.3:
        return 2
    return 3


def _is_heading(text: str, size: float, body: float) -> bool:
    if len(text) > 120:
        return False
    if MULTILEVEL_HEADING_RE.match(text) or SIMPLE_HEADING_RE.match(text):
        return True
    return size >= body * HEADING_SIZE_RATIO


def _line_box(line: dict[str, Any]) -> BoundingBox:
    return BoundingBox(x0=line["x0"], top=line["top"], x1=line["x1"], bottom=line["bottom"])


def _text_blocks(
    lines: list[dict[str, Any]],
    page_number: int,
    body: float,
    repeated: set[str],
    diagnostics: ExtractionDiagnostics,
) -> list[BlockLike]:
    if not lines:
        return []

    heights = [line["bottom"] - line["top"] for line in lines if line["bottom"] > line["top"]]
    line_height = statistics.median(heights) if heights else 12.0
    gap_threshold = line_height * PARAGRAPH_GAP_RATIO

    blocks: list[BlockLike] = []
    paragraph: list[dict[str, Any]] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if not paragraph:
            return
        text = " ".join(line["text"].strip() for line in paragraph).strip()
        if text:
            box = BoundingBox(
                x0=min(line["x0"] for line in paragraph),
                top=min(line["top"] for line in paragraph),
                x1=max(line["x1"] for line in paragraph),
                bottom=max(line["bottom"] for line in paragraph),
            )
            blocks.append(
                Paragraph(
                    text=text,
                    page=page_number,
                    bbox=box,
                    repeated_layout=text in repeated,
                )
            )
        paragraph = []

    for line in lines:
        text = (line.get("text") or "").strip()
        if not text:
            continue
        size = _line_size(line)
        is_list = bool(LIST_RE.match(text))
        is_heading = _is_heading(text, size, body)

        if is_heading:
            flush_paragraph()
            blocks.append(
                Heading(
                    text=text,
                    level=_heading_level(text, size, body),
                    page=page_number,
                    bbox=_line_box(line),
                )
            )
            continue

        if is_list:
            flush_paragraph()
            match = LIST_RE.match(text)
            marker = match.group("marker") if match else ""
            item = ListItem(
                text=text[match.end() :].strip() if match else text,
                marker=marker,
                ordered=marker[:1].isdigit(),
                page=page_number,
                bbox=_line_box(line),
            )
            if blocks and isinstance(blocks[-1], ListBlock):
                blocks[-1].items.append(item)
            else:
                blocks.append(ListBlock(items=[item], ordered=item.ordered, page=page_number))
            diagnostics.list_items += 1
            continue

        if paragraph and line["top"] - paragraph[-1]["bottom"] > gap_threshold:
            flush_paragraph()
        paragraph.append(line)

    flush_paragraph()
    return blocks


def _table_header(rows: list[list[str | None]]) -> list[str]:
    if len(rows) < MIN_TABLE_ROWS:
        return []
    first = [" ".join(str(cell or "").split()) for cell in rows[0]]
    if not all(first):
        return []
    if any(NUMBERISH_RE.match(cell) for cell in first):
        return []
    return first


def _table_is_suspicious(rows: list[list[str | None]]) -> bool:
    if not rows:
        return True
    widths = {len(row) for row in rows}
    if len(widths) > 1:
        return True
    empty_ratio = sum(1 for row in rows for cell in row if not (cell or "").strip()) / max(
        1, sum(len(row) for row in rows)
    )
    return empty_ratio > 0.6


def _table_block(
    rows: list[list[str | None]],
    page_number: int,
    sequence: int,
    bbox: tuple[float, float, float, float] | None,
    diagnostics: ExtractionDiagnostics,
) -> TableBlock:
    header = _table_header(rows)
    data_rows = rows[1:] if header else rows
    table_id = f"page{page_number}-table{sequence}"

    table_rows: list[TableRow] = []
    for row_index, raw in enumerate(data_rows):
        cells: list[TableCell] = []
        for column_index, value in enumerate(raw):
            text = " ".join(str(value).split()) if value else ""
            header_name = header[column_index] if column_index < len(header) else None
            cells.append(TableCell(text=text, column_index=column_index, header=header_name))
        table_rows.append(TableRow(index=row_index, cells=cells))

    diagnostics.tables_detected += 1
    diagnostics.rows_detected += len(table_rows)
    diagnostics.cells_detected += sum(len(row.cells) for row in table_rows)

    return TableBlock(
        table_id=table_id,
        header=header,
        rows=table_rows,
        page=page_number,
        bbox=_bbox(bbox) if bbox else None,
        suspicious=_table_is_suspicious(rows),
    )


def _fallback_table_valid(rows: list[list[str | None]]) -> bool:
    header = _table_header(rows)
    if not header:
        return False
    if not (MIN_TABLE_COLS <= len(header) <= 10):
        return False
    widths = {len(row) for row in rows}
    if widths != {len(header)}:
        return False
    return all(len(str(cell or "")) <= 120 for row in rows for cell in row)


def _find_tables(page) -> list:
    try:
        tables = page.find_tables()
    except Exception as exc:  # pragma: no cover - pdfplumber internal failure
        logger.warning("table detection failed: %s", exc)
        return []
    if tables:
        return tables
    try:
        candidate = page.find_tables(
            table_settings={"vertical_strategy": "text", "horizontal_strategy": "text"}
        )
    except Exception as exc:  # pragma: no cover - pdfplumber internal failure
        logger.warning("borderless table detection failed: %s", exc)
        return []
    return [table for table in candidate if _fallback_table_valid(table.extract() or [])]


class PdfParser(DocumentParser):
    mime_types = ("application/pdf",)

    def parse(self, content: bytes, *, source: str | None = None) -> Document:
        diagnostics = ExtractionDiagnostics()
        blocks: list[BlockLike] = []

        with pdfplumber.open(BytesIO(content)) as pdf:
            pages = pdf.pages
            diagnostics.pages = len(pages)
            repeated = _detect_repeated(pages, diagnostics)

            previous_table: TableBlock | None = None
            previous_bottom = 0.0

            for page_number, page in enumerate(pages, start=1):
                try:
                    page_blocks, previous_table, previous_bottom = self._process_page(
                        page,
                        page_number,
                        repeated,
                        diagnostics,
                        previous_table,
                        previous_bottom,
                    )
                    blocks.extend(page_blocks)
                except Exception as exc:
                    diagnostics.add_warning(f"page {page_number} failed: {exc}")
                    logger.warning("pdf page %s failed: %s", page_number, exc)

        document = Document(
            source=source, page_count=diagnostics.pages, blocks=blocks, diagnostics=diagnostics
        )
        for warning in diagnostics.warnings:
            logger.debug("pdf warning: %s", warning)
        return document

    def _process_page(
        self,
        page,
        page_number: int,
        repeated: set[str],
        diagnostics: ExtractionDiagnostics,
        previous_table: TableBlock | None,
        previous_bottom: float,
    ) -> tuple[list[BlockLike], TableBlock | None, float]:
        page_height = page.height or 0.0
        tables = _find_tables(page)
        boxes = [table.bbox for table in tables]

        lines = [
            line for line in page.extract_text_lines() if not _in_any_bbox(boxes, line)
        ]
        lines.sort(key=lambda line: (round(line["top"], 1), line["x0"]))
        body = _body_size(lines)

        items: list[tuple[float, BlockLike]] = []
        for block in _text_blocks(lines, page_number, body, repeated, diagnostics):
            top = block.bbox.top if block.bbox else 0.0
            items.append((top, block))

        for sequence, table in enumerate(tables, start=1):
            try:
                rows = table.extract() or []
            except Exception as exc:
                diagnostics.add_warning(f"table {sequence} on page {page_number} failed: {exc}")
                logger.warning("pdf table %s page %s failed: %s", sequence, page_number, exc)
                continue
            if not rows:
                diagnostics.add_warning(f"empty table on page {page_number}")
                continue
            table_top = table.bbox[1]
            header = _table_header(rows)
            merges = (
                previous_table is not None
                and page_number > 1
                and table_top < page_height * CONTINUATION_TOP_RATIO
                and previous_bottom > page_height * 0.6
                and bool(header)
                and header == previous_table.header
            )
            if merges and previous_table is not None:
                offset = len(previous_table.rows)
                for row_index, raw in enumerate(rows[1:]):
                    cells = [
                        TableCell(
                            text=" ".join(str(value).split()) if value else "",
                            column_index=column_index,
                            header=header[column_index] if column_index < len(header) else None,
                        )
                        for column_index, value in enumerate(raw)
                    ]
                    previous_table.rows.append(TableRow(index=offset + row_index, cells=cells))
                previous_table.continues_previous = True
                diagnostics.add_warning(f"table continued across pages at page {page_number}")
                continue

            block = _table_block(rows, page_number, sequence, table.bbox, diagnostics)
            items.append((table_top, block))
            previous_table = block

        items.sort(key=lambda item: item[0])
        page_blocks = [block for _, block in items]
        if tables:
            previous_bottom = max(table.bbox[3] for table in tables)
        return page_blocks, previous_table, previous_bottom


def _detect_repeated(pages: list, diagnostics: ExtractionDiagnostics) -> set[str]:
    if len(pages) < 2:
        return set()
    threshold = max(2, math.ceil(len(pages) * REPEATED_PAGE_RATIO))
    seen: dict[str, set[int]] = {}
    for page_number, page in enumerate(pages, start=1):
        try:
            lines = page.extract_text_lines()
        except Exception as exc:
            diagnostics.add_warning(f"repeated-layout scan failed on page {page_number}: {exc}")
            continue
        height = page.height or 0.0
        for line in lines:
            text = (line.get("text") or "").strip()
            if not text:
                continue
            top, bottom = line["top"], line["bottom"]
            if height and (
                top < height * HEADER_FOOTER_ZONE or bottom > height * (1 - HEADER_FOOTER_ZONE)
            ):
                seen.setdefault(text, set()).add(page_number)
    return {text for text, page_numbers in seen.items() if len(page_numbers) >= threshold}
