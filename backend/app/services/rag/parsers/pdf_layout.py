"""Coordinate-aware, parser-internal PDF representation.

This is the bridge between raw ``pdfplumber`` output and the final IR: words
keep their page and bounding box so a later, deterministic stage can rebuild
rows and spatial relations without relying on semantic similarity or an LLM.
It is intentionally PDF-specific and not part of the Common IR.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

import pdfplumber

HEADER_FOOTER_ZONE = 0.12
ROW_TOLERANCE_RATIO = 0.4
COLUMN_GAP_RATIO = 1.2
MIN_COLUMN_GAP = 6.0
MIN_ROW_TOLERANCE = 0.5
COLUMN_MATCH_TOLERANCE = 15.0


@dataclass(frozen=True)
class PdfToken:
    text: str
    page: int
    x0: float
    x1: float
    top: float
    bottom: float
    size: float = 0.0
    source: str = "text"

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass(frozen=True)
class PageLayout:
    page: int
    width: float
    height: float
    tokens: tuple[PdfToken, ...]

    def relative_box(self, token: PdfToken) -> tuple[float, float, float, float]:
        """Normalized ``(x0, top, x1, bottom)`` as ratios of the page size."""
        if self.width <= 0 or self.height <= 0:
            return (0.0, 0.0, 0.0, 0.0)
        return (
            token.x0 / self.width,
            token.top / self.height,
            token.x1 / self.width,
            token.bottom / self.height,
        )

    def relative_x(self, token: PdfToken) -> float:
        return token.x0 / self.width if self.width > 0 else 0.0

    def relative_y(self, token: PdfToken) -> float:
        return token.top / self.height if self.height > 0 else 0.0

    def in_header_zone(self, token: PdfToken, ratio: float = HEADER_FOOTER_ZONE) -> bool:
        return self.height > 0 and token.top < self.height * ratio

    def in_footer_zone(self, token: PdfToken, ratio: float = HEADER_FOOTER_ZONE) -> bool:
        return self.height > 0 and token.bottom > self.height * (1 - ratio)


def extract_tokens(page, page_number: int) -> tuple[PdfToken, ...]:
    words = page.extract_words(extra_attrs=["size"]) or []
    tokens = []
    for word in words:
        text = word.get("text")
        if not text:
            continue
        tokens.append(
            PdfToken(
                text=text,
                page=page_number,
                x0=float(word["x0"]),
                x1=float(word["x1"]),
                top=float(word["top"]),
                bottom=float(word["bottom"]),
                size=float(word.get("size") or 0.0),
            )
        )
    return tuple(tokens)


def build_page_layout(page: pdfplumber.page.Page, page_number: int) -> PageLayout:
    return PageLayout(
        page=page_number,
        width=float(page.width or 0.0),
        height=float(page.height or 0.0),
        tokens=extract_tokens(page, page_number),
    )


@dataclass(frozen=True)
class PdfCell:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    tokens: tuple[PdfToken, ...]


@dataclass(frozen=True)
class PdfRow:
    page: int
    top: float
    bottom: float
    tokens: tuple[PdfToken, ...]
    cells: tuple[PdfCell, ...]

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def text(self) -> str:
        return " ".join(token.text for token in sorted(self.tokens, key=lambda t: t.x0))


def _median_positive(values) -> float:
    items = [value for value in values if value > 0]
    return statistics.median(items) if items else 0.0


def default_row_tolerance(tokens) -> float:
    heights = _median_positive(token.height for token in tokens)
    return max(heights * ROW_TOLERANCE_RATIO, MIN_ROW_TOLERANCE)


def default_column_gap(tokens) -> float:
    heights = _median_positive(token.height for token in tokens)
    return max(heights * COLUMN_GAP_RATIO, MIN_COLUMN_GAP)


def _cell_from_tokens(tokens) -> PdfCell:
    ordered = tuple(sorted(tokens, key=lambda token: token.x0))
    return PdfCell(
        text=" ".join(token.text for token in ordered),
        x0=min(token.x0 for token in ordered),
        x1=max(token.x1 for token in ordered),
        top=min(token.top for token in ordered),
        bottom=max(token.bottom for token in ordered),
        tokens=ordered,
    )


def split_row_cells(tokens, column_gap: float | None = None) -> tuple[PdfCell, ...]:
    """Split tokens of one row into visual cells by horizontal gaps."""
    ordered = sorted(tokens, key=lambda token: token.x0)
    if not ordered:
        return ()
    threshold = column_gap if column_gap is not None else default_column_gap(ordered)
    cells: list[PdfCell] = []
    current = [ordered[0]]
    for previous, token in zip(ordered, ordered[1:]):
        if token.x0 - previous.x1 >= threshold:
            cells.append(_cell_from_tokens(current))
            current = [token]
        else:
            current.append(token)
    cells.append(_cell_from_tokens(current))
    return tuple(cells)


def group_rows(
    tokens,
    *,
    tolerance: float | None = None,
    column_gap: float | None = None,
) -> tuple[PdfRow, ...]:
    """Group tokens into visual rows by vertical position (deterministic)."""
    ordered = sorted(tokens, key=lambda token: (token.center_y, token.x0))
    if not ordered:
        return ()
    resolved = tolerance if tolerance is not None else default_row_tolerance(ordered)
    rows: list[PdfRow] = []
    current = [ordered[0]]
    top, bottom = ordered[0].top, ordered[0].bottom
    for token in ordered[1:]:
        center = (top + bottom) / 2
        if abs(token.center_y - center) <= resolved:
            current.append(token)
            top = min(top, token.top)
            bottom = max(bottom, token.bottom)
        else:
            rows.append(
                PdfRow(
                    page=current[0].page,
                    top=min(t.top for t in current),
                    bottom=max(t.bottom for t in current),
                    tokens=tuple(current),
                    cells=split_row_cells(current, column_gap),
                )
            )
            current = [token]
            top, bottom = token.top, token.bottom
    rows.append(
        PdfRow(
            page=current[0].page,
            top=min(t.top for t in current),
            bottom=max(t.bottom for t in current),
            tokens=tuple(current),
            cells=split_row_cells(current, column_gap),
        )
    )
    return tuple(rows)


def tokens_in_band(tokens, top: float, bottom: float) -> tuple[PdfToken, ...]:
    """Tokens whose vertical center falls inside the band (no neighbour bleed)."""
    return tuple(
        token for token in tokens if top <= token.center_y <= bottom
    )


def _has_letters(text: str) -> bool:
    return any(character.isalpha() for character in text)


def _is_value_like(text: str) -> bool:
    return any(character.isdigit() for character in text) and not _has_letters(text)


def _row_is_header(cells: tuple[PdfCell, ...]) -> bool:
    if len(cells) < 2:
        return False
    if any(_is_value_like(cell.text) for cell in cells):
        return False
    return any(_has_letters(cell.text) for cell in cells)


def _matching_header(
    cell: PdfCell, headers: list[tuple[float, float, str]]
) -> str | None:
    best_label: str | None = None
    best_overlap = 0.0
    for x0, x1, label in headers:
        overlap = min(cell.x1, x1) - max(cell.x0, x0)
        if overlap > best_overlap:
            best_overlap = overlap
            best_label = label
    if best_overlap > 0:
        return best_label
    center = (cell.x0 + cell.x1) / 2
    for x0, x1, label in headers:
        if x0 - COLUMN_MATCH_TOLERANCE <= center <= x1 + COLUMN_MATCH_TOLERANCE:
            return label
    return None


def header_label_map(tokens, column_gap: float | None = None) -> dict[int, str]:
    """Map each value token to the label of its column.

    A header row (all cells textual, at least two cells) defines the columns;
    the value cells below are matched to a column by horizontal position. This
    links a column header like "NETTO IN BUSTA" to the value in its column even
    when they are on different rows.
    """
    mapping: dict[int, str] = {}
    headers: list[tuple[float, float, str]] | None = None
    for row in group_rows(tokens, column_gap=column_gap):
        if _row_is_header(row.cells):
            headers = [(cell.x0, cell.x1, cell.text) for cell in row.cells]
            continue
        if not headers:
            continue
        for cell in row.cells:
            if not _is_value_like(cell.text):
                continue
            label = _matching_header(cell, headers)
            if label:
                for token in cell.tokens:
                    mapping[id(token)] = label
    return mapping


def _cell_column_label(cell: PdfCell, labels: dict[int, str]) -> str | None:
    for token in cell.tokens:
        label = labels.get(id(token))
        if label:
            return label
    return None


def _join_cells(cells: tuple[PdfCell, ...], labels: dict[int, str]) -> str:
    parts: list[str] = []
    index = 0
    while index < len(cells):
        cell = cells[index]
        column_label = _cell_column_label(cell, labels)
        if column_label:
            parts.append(f"{column_label}: {cell.text}")
            index += 1
            continue
        if (
            _has_letters(cell.text)
            and index + 1 < len(cells)
            and _is_value_like(cells[index + 1].text)
        ):
            parts.append(f"{cell.text}: {cells[index + 1].text}")
            index += 2
            continue
        parts.append(cell.text)
        index += 1
    return "  ".join(parts)


def reconstruct_line_text(
    tokens,
    column_gap: float | None = None,
    labels: dict[int, str] | None = None,
) -> str:
    """Reconstruct a line preserving columns and label/value relations.

    Single-cell lines keep their natural text; multi-cell lines separate cells
    with double spaces and render ``label value`` pairs as ``label: value``.
    ``labels`` maps value tokens to the header of their column when known.
    """
    ordered = sorted(tokens, key=lambda token: token.x0)
    if not ordered:
        return ""
    cells = split_row_cells(ordered, column_gap)
    if len(cells) == 1:
        return " ".join(token.text for token in ordered)
    return _join_cells(cells, labels or {})
