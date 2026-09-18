import pytest

from app.services.rag.chunker import Chunk, chunk_text


def test_chunk_text_returns_empty_for_blank_input():
    assert chunk_text("   \n  ", chunk_size=100, chunk_overlap=10) == []


def test_chunk_text_returns_single_chunk_for_short_text():
    chunks = chunk_text("Short text", chunk_size=100, chunk_overlap=10)

    assert len(chunks) == 1
    assert chunks[0].text == "Short text"
    assert chunks[0].index == 0


def test_chunk_text_splits_long_text():
    text = "parola " * 500

    chunks = chunk_text(text, chunk_size=200, chunk_overlap=20)

    assert len(chunks) > 1
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert all(len(chunk.text) <= 220 for chunk in chunks)


def test_chunk_text_prefers_paragraph_separator():
    text = "Primo blocco.\n\nSecondo blocco.\n\nTerzo blocco."

    chunks = chunk_text(text, chunk_size=20, chunk_overlap=0)

    assert chunks[0].text == "Primo blocco."


def test_chunk_text_applies_overlap():
    text = "a" * 100

    chunks = chunk_text(text, chunk_size=60, chunk_overlap=10)

    assert len(chunks) == 2
    assert chunks[1].text.startswith(chunks[0].text[-10:])


def test_chunk_text_handles_no_separators_with_hard_split():
    text = "x" * 250

    chunks = chunk_text(text, chunk_size=100, chunk_overlap=0)

    assert len(chunks) == 3
    assert chunks[0].text == "x" * 100


def test_chunk_text_strips_each_chunk():
    chunks = chunk_text("  ciao  \n\n  mondo  ", chunk_size=5, chunk_overlap=0)

    assert all(chunk.text == chunk.text.strip() for chunk in chunks)


def test_chunk_text_accepts_custom_separators():
    chunks = chunk_text("a|b|c", chunk_size=3, chunk_overlap=0, separators=["|", ""])

    assert [chunk.text for chunk in chunks] == ["a|", "b|c"]


def test_chunk_text_rejects_invalid_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("text", chunk_size=0, chunk_overlap=0)


def test_chunk_text_rejects_overlap_not_smaller_than_size():
    with pytest.raises(ValueError):
        chunk_text("text", chunk_size=10, chunk_overlap=10)


def test_chunk_text_rejects_negative_overlap():
    with pytest.raises(ValueError):
        chunk_text("text", chunk_size=10, chunk_overlap=-1)


def test_chunk_is_frozen_dataclass():
    chunk = Chunk(index=1, text="hello")

    with pytest.raises(Exception):
        chunk.index = 2
