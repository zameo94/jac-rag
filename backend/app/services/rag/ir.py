"""Common Document Intermediate Representation (IR) shared by every parser.

Parsers (PDF, DOCX, Markdown, TXT, ...) translate their format-specific layout
into these structures. The chunker and the ingestion pipeline only ever see this
IR, never format-specific objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar


class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    FIGURE = "figure"
    CODE = "code"
    QUOTE = "quote"
    GENERIC = "generic"


@dataclass(frozen=True, kw_only=True)
class BoundingBox:
    x0: float
    top: float
    x1: float
    bottom: float


@dataclass(kw_only=True)
class TableCell:
    text: str = ""
    column_index: int = 0
    header: str | None = None
    row_span: int = 1
    col_span: int = 1

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass(kw_only=True)
class TableRow:
    index: int = 0
    cells: list[TableCell] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return all(cell.is_empty for cell in self.cells)

    def cell_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for cell in self.cells:
            key = cell.header or f"col_{cell.column_index + 1}"
            result[key] = cell.text
        return result


@dataclass(kw_only=True)
class Block:
    """Base block. Subclasses declare their own ``kind``."""

    kind: ClassVar[BlockType] = BlockType.GENERIC

    page: int | None = None
    order: int = 0
    bbox: BoundingBox | None = None
    section_path: tuple[str, ...] = ()
    source_block_id: str | None = None
    repeated_layout: bool = False

    @property
    def type(self) -> BlockType:
        return type(self).kind


@dataclass(kw_only=True)
class Heading(Block):
    kind: ClassVar[BlockType] = BlockType.HEADING

    text: str = ""
    level: int = 1


@dataclass(kw_only=True)
class Paragraph(Block):
    kind: ClassVar[BlockType] = BlockType.PARAGRAPH

    text: str = ""


@dataclass(kw_only=True)
class ListItem(Block):
    kind: ClassVar[BlockType] = BlockType.LIST_ITEM

    text: str = ""
    marker: str = ""
    ordered: bool = False


@dataclass(kw_only=True)
class ListBlock(Block):
    kind: ClassVar[BlockType] = BlockType.LIST

    items: list[ListItem] = field(default_factory=list)
    ordered: bool = False


@dataclass(kw_only=True)
class TableBlock(Block):
    kind: ClassVar[BlockType] = BlockType.TABLE

    table_id: str = ""
    header: list[str] = field(default_factory=list)
    rows: list[TableRow] = field(default_factory=list)
    caption: str | None = None
    continues_previous: bool = False
    suspicious: bool = False


@dataclass(kw_only=True)
class FigureBlock(Block):
    kind: ClassVar[BlockType] = BlockType.FIGURE

    caption: str = ""


@dataclass(kw_only=True)
class CodeBlock(Block):
    kind: ClassVar[BlockType] = BlockType.CODE

    text: str = ""
    language: str | None = None


@dataclass(kw_only=True)
class QuoteBlock(Block):
    kind: ClassVar[BlockType] = BlockType.QUOTE

    text: str = ""


@dataclass(kw_only=True)
class GenericBlock(Block):
    kind: ClassVar[BlockType] = BlockType.GENERIC

    text: str = ""


BlockLike = (
    Heading
    | Paragraph
    | ListItem
    | ListBlock
    | TableBlock
    | FigureBlock
    | CodeBlock
    | QuoteBlock
    | GenericBlock
)


@dataclass(kw_only=True)
class Document:
    """Root of the Common IR."""

    source: str | None = None
    page_count: int = 0
    blocks: list[BlockLike] = field(default_factory=list)
    diagnostics: "ExtractionDiagnostics" = field(default_factory=lambda: _empty_diagnostics())
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Semantic serialization of the whole document, in reading order."""
        from app.services.rag.serialization import serialize_document

        return serialize_document(self)

    @property
    def chars_per_page(self) -> float:
        if self.page_count <= 0:
            return float(len(self.text))
        return len(self.text) / self.page_count

    def has_text_layer(self) -> bool:
        from app.core.config import get_settings

        return self.chars_per_page >= get_settings().min_chars_per_page

    def iter_tables(self):
        for block in self.blocks:
            if isinstance(block, TableBlock):
                yield block


def _empty_diagnostics() -> "ExtractionDiagnostics":
    from app.services.rag.diagnostics import ExtractionDiagnostics

    return ExtractionDiagnostics()
