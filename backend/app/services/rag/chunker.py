from dataclasses import dataclass

DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""]


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str


def _split_text(text: str, separators: list[str], chunk_size: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text else []

    separator = separators[0]
    remaining = separators[1:]
    if separator == "":
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    parts = text.split(separator)
    pieces: list[str] = []
    for position, part in enumerate(parts):
        is_last = position == len(parts) - 1
        segment = part if is_last else part + separator
        if not segment:
            continue
        if len(segment) > chunk_size:
            pieces.extend(_split_text(segment, remaining, chunk_size))
        else:
            pieces.append(segment)
    return pieces


def _merge_pieces(pieces: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if not current:
            current = piece
            continue
        if len(current) + len(piece) <= chunk_size:
            current += piece
        else:
            chunks.append(current)
            overlap = current[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = overlap + piece
    if current:
        chunks.append(current)
    return chunks


def chunk_text(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    separators: list[str] | None = None,
) -> list[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size")

    normalized = text.strip()
    if not normalized:
        return []

    pieces = _split_text(normalized, separators or DEFAULT_SEPARATORS, chunk_size)
    merged = _merge_pieces(pieces, chunk_size, chunk_overlap)
    return [
        Chunk(index=index, text=chunk.strip())
        for index, chunk in enumerate(merged)
        if chunk.strip()
    ]
