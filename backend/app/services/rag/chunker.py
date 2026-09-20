from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from app.services.rag.ir import (
    BlockType,
    CodeBlock,
    FigureBlock,
    GenericBlock,
    Heading,
    ListBlock,
    Paragraph,
    QuoteBlock,
    TableBlock,
)
from app.services.rag.serialization import (
    serialize_table_row,
    table_context_lines,
)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ChunkMetadata:
    page: int | None = None
    block_type: BlockType | None = None
    section: tuple[str, ...] = ()
    table_id: str | None = None
    row_indices: tuple[int, ...] = ()
    source_block_ids: tuple[str, ...] = ()
    oversized: bool = False


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)


@dataclass(frozen=True)
class ChunkingConfig:
    target_size: int
    max_size: int
    overlap: int
    table_context: bool = True
    section_context: bool = True
    include_metadata: bool = True

    def __post_init__(self) -> None:
        if self.target_size <= 0:
            raise ValueError("target_size must be positive")
        if self.max_size < self.target_size:
            raise ValueError("max_size must be >= target_size")
        if self.overlap < 0 or self.overlap >= self.target_size:
            raise ValueError("overlap must be >= 0 and < target_size")


# --------------------------------------------------------------------------- #
# Structure-aware chunker over the Common IR                                   #
# --------------------------------------------------------------------------- #


@dataclass
class _Unit:
    text: str
    group: str
    context: tuple[str, ...] = ()
    block_type: BlockType = BlockType.GENERIC
    page: int | None = None
    section: tuple[str, ...] = ()
    table_id: str | None = None
    row_index: int | None = None
    source_block_id: str | None = None
    atomic: bool = False
    oversized: bool = False


def _section_line(section: tuple[str, ...], config: ChunkingConfig) -> tuple[str, ...]:
    if not config.section_context or not section:
        return ()
    return (f"Sezione: {' > '.join(section)}",)


def _expand_oversized(units: list[_Unit], config: ChunkingConfig) -> list[_Unit]:
    expanded: list[_Unit] = []
    for unit in units:
        if len(unit.text) <= config.max_size:
            expanded.append(unit)
        elif unit.atomic:
            expanded.append(replace(unit, oversized=True))
        else:
            for part in _split_oversized_text(unit.text, config.max_size):
                expanded.append(replace(unit, text=part, oversized=True))
    return expanded


def _split_oversized_text(text: str, max_size: int) -> list[str]:
    sentences = [chunk for chunk in _SENTENCE_RE.split(text) if chunk]
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_size:
            if current:
                parts.append(current)
                current = ""
            parts.extend(
                sentence[i : i + max_size] for i in range(0, len(sentence), max_size)
            )
            continue
        if current and len(current) + len(sentence) + 1 > max_size:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip() if current else sentence
    if current:
        parts.append(current)
    return [part for part in parts if part.strip()]


def _content_section_paths(document) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(block.section_path)
        for block in document.blocks
        if not isinstance(block, Heading)
    )


def _heading_is_propagated(heading: Heading, content_paths: tuple[tuple[str, ...], ...]) -> bool:
    """True when the heading's section (or a descendant) holds content.

    In that case the heading title already travels inside the content chunk via
    the ``Sezione:`` context line, so the heading must not become a competing
    standalone chunk.
    """
    own_path = tuple(heading.section_path) + (heading.text,)
    return any(path[: len(own_path)] == own_path for path in content_paths)


def _units_from_document(document, config: ChunkingConfig) -> list[_Unit]:
    units: list[_Unit] = []
    section_counter = 0
    content_paths = _content_section_paths(document)

    for block in document.blocks:
        if isinstance(block, Heading):
            section_counter += 1
            if _heading_is_propagated(block, content_paths):
                continue
            context = _section_line(block.section_path, config)
            units.append(
                _Unit(
                    text=f"Titolo: {block.text.strip()}",
                    group=f"heading-{block.order}",
                    context=context,
                    block_type=BlockType.HEADING,
                    page=block.page,
                    section=block.section_path,
                    source_block_id=block.source_block_id,
                )
            )
        elif isinstance(block, Paragraph):
            units.append(
                _Unit(
                    text=block.text.strip(),
                    group=f"prose-{section_counter}",
                    context=_section_line(block.section_path, config),
                    block_type=BlockType.PARAGRAPH,
                    page=block.page,
                    section=block.section_path,
                    source_block_id=block.source_block_id,
                )
            )
        elif isinstance(block, ListBlock):
            context = _section_line(block.section_path, config)
            for item in block.items:
                text = f"{item.marker} {item.text}".strip()
                if not text:
                    continue
                units.append(
                    _Unit(
                        text=text,
                        group=f"list-{block.source_block_id}",
                        context=context,
                        block_type=BlockType.LIST_ITEM,
                        page=block.page,
                        section=block.section_path,
                        source_block_id=item.source_block_id or block.source_block_id,
                        atomic=True,
                    )
                )
        elif isinstance(block, TableBlock):
            context = (
                tuple(table_context_lines(block, section_path=block.section_path))
                if config.table_context
                else _section_line(block.section_path, config)
            )
            for row in block.rows:
                if row.is_empty:
                    continue
                units.append(
                    _Unit(
                        text=serialize_table_row(block, row),
                        group=f"table-{block.table_id}",
                        context=context,
                        block_type=BlockType.TABLE_ROW,
                        page=block.page,
                        section=block.section_path,
                        table_id=block.table_id,
                        row_index=row.index,
                        source_block_id=block.source_block_id,
                        atomic=True,
                    )
                )
        elif isinstance(block, FigureBlock):
            if block.caption.strip():
                units.append(
                    _Unit(
                        text=block.caption.strip(),
                        group=f"prose-{section_counter}",
                        context=_section_line(block.section_path, config),
                        block_type=BlockType.FIGURE,
                        page=block.page,
                        section=block.section_path,
                        source_block_id=block.source_block_id,
                    )
                )
        elif isinstance(block, CodeBlock | QuoteBlock | GenericBlock):
            if block.text.strip():
                units.append(
                    _Unit(
                        text=block.text.strip(),
                        group=f"prose-{section_counter}",
                        context=_section_line(block.section_path, config),
                        block_type=block.type,
                        page=block.page,
                        section=block.section_path,
                        source_block_id=block.source_block_id,
                    )
                )

    return units


def _tail(text: str, size: int) -> str:
    if size <= 0 or len(text) <= size:
        return text if size > 0 else ""
    tail = text[-size:]
    space = tail.find(" ")
    if space != -1 and space < len(tail) - 1:
        tail = tail[space + 1 :]
    return tail.strip()


def _is_prose(group: str) -> bool:
    return group.startswith("prose-")


def _unique(values) -> tuple:
    seen: set = set()
    ordered: list = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)


def _structured_header(
    section: tuple[str, ...], context: tuple[str, ...], config: ChunkingConfig
) -> list[str]:
    """Structured header: Documento / Sezione / Colonne / Contenuto."""
    header: list[str] = []
    if config.section_context and section:
        header.append(f"Documento: {section[0]}")
        if len(section) > 1:
            header.append(f"Sezione: {' > '.join(section[1:])}")
    if config.table_context:
        for line in context:
            if line.startswith("Colonne:") or line.startswith("Tabella:"):
                header.append(line)
    header.append("Contenuto:")
    return header


def chunk_document(document, config: ChunkingConfig) -> list[Chunk]:
    units = _expand_oversized(_units_from_document(document, config), config)
    if not units:
        return []

    chunks: list[Chunk] = []
    current: list[_Unit] = []
    current_group = ""
    current_context: tuple[str, ...] = ()
    current_text_len = 0
    pending_overlap = ""

    def flush(overlap_next: bool) -> None:
        nonlocal current, current_group, current_context, current_text_len, pending_overlap
        if not current:
            return
        body = "\n".join(unit.text for unit in current)
        prefix = pending_overlap
        pending_overlap = ""
        if prefix:
            body = f"{prefix}\n{body}"
        header = _structured_header(current[0].section, current_context, config)
        text = "\n".join(header + [body])
        metadata = ChunkMetadata(
            page=current[0].page,
            block_type=current[0].block_type,
            section=current[0].section,
            table_id=current[0].table_id,
            row_indices=_unique(
                unit.row_index for unit in current if unit.row_index is not None
            ),
            source_block_ids=_unique(
                unit.source_block_id for unit in current if unit.source_block_id
            ),
            oversized=any(unit.oversized for unit in current),
        )
        if not config.include_metadata:
            metadata = ChunkMetadata()
        chunks.append(Chunk(index=len(chunks), text=text.strip(), metadata=metadata))
        if overlap_next and _is_prose(current_group) and config.overlap > 0:
            pending_overlap = _tail(body, config.overlap)
        current = []
        current_text_len = 0

    for unit in units:
        if not current:
            current = [unit]
            current_group = unit.group
            current_context = unit.context
            current_text_len = len(unit.text)
            continue

        same_group = unit.group == current_group
        would_overflow = current_text_len + len(unit.text) + 1 > config.target_size

        if not same_group:
            flush(overlap_next=False)
            current = [unit]
            current_group = unit.group
            current_context = unit.context
            current_text_len = len(unit.text)
            continue

        if would_overflow:
            flush(overlap_next=True)
            current = [unit]
            current_group = unit.group
            current_context = unit.context
            current_text_len = len(unit.text)
            continue

        current.append(unit)
        current_text_len += len(unit.text) + 1

    flush(overlap_next=False)

    oversized = sum(1 for chunk in chunks if chunk.metadata.oversized)
    try:
        document.diagnostics.oversized_blocks += oversized
    except AttributeError:
        pass

    return chunks
