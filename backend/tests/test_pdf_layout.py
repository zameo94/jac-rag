from io import BytesIO

import pdfplumber

from app.services.rag.parsers.pdf_layout import (
    PdfToken,
    PageLayout,
    build_page_layout,
    extract_tokens,
    group_rows,
    header_label_map,
    reconstruct_line_text,
    split_row_cells,
    tokens_in_band,
)
from tests.fixtures import build_pdf


def token(text: str, x0: float, x1: float, top: float, bottom: float) -> PdfToken:
    return PdfToken(text=text, page=1, x0=x0, x1=x1, top=top, bottom=bottom)


def tok(
    text: str,
    x0: float,
    x1: float,
    top: float,
    height: float = 9.0,
) -> PdfToken:
    return PdfToken(text=text, page=1, x0=x0, x1=x1, top=top, bottom=top + height, size=9.0)


def test_pdf_token_geometry_properties():
    item = token("ciao", 10.0, 30.0, 5.0, 15.0)

    assert item.width == 20.0
    assert item.height == 10.0
    assert item.center_x == 20.0
    assert item.center_y == 10.0


def test_page_layout_relative_box_and_axes():
    item = token("ciao", 20.0, 40.0, 50.0, 60.0)
    layout = PageLayout(page=1, width=100.0, height=200.0, tokens=(item,))

    assert layout.relative_box(item) == (0.2, 0.25, 0.4, 0.3)
    assert layout.relative_x(item) == 0.2
    assert layout.relative_y(item) == 0.25


def test_page_layout_zones():
    layout = PageLayout(page=1, width=100.0, height=200.0, tokens=())
    header = token("h", 0.0, 10.0, 5.0, 15.0)
    body = token("b", 0.0, 10.0, 90.0, 110.0)
    footer = token("f", 0.0, 10.0, 185.0, 195.0)

    assert layout.in_header_zone(header) is True
    assert layout.in_header_zone(body) is False
    assert layout.in_footer_zone(footer) is True
    assert layout.in_footer_zone(body) is False


def test_page_layout_zero_size_page_is_safe():
    item = token("ciao", 1.0, 2.0, 3.0, 4.0)
    layout = PageLayout(page=1, width=0.0, height=0.0, tokens=(item,))

    assert layout.relative_box(item) == (0.0, 0.0, 0.0, 0.0)
    assert layout.relative_x(item) == 0.0
    assert layout.relative_y(item) == 0.0
    assert layout.in_header_zone(item) is False
    assert layout.in_footer_zone(item) is False


def test_extract_tokens_from_pdf_keeps_coordinates_and_page():
    pdf = build_pdf([("text", "Contenuto di prova")])

    with pdfplumber.open(BytesIO(pdf)) as document:
        page = document.pages[0]
        tokens = extract_tokens(page, 1)

    assert tokens
    assert all(item.page == 1 for item in tokens)
    assert all(item.x0 <= item.x1 and item.top <= item.bottom for item in tokens)
    assert "prova" in " ".join(item.text for item in tokens)


def test_build_page_layout_from_pdf_has_page_size_and_tokens():
    pdf = build_pdf([("text", "Riga uno")])

    with pdfplumber.open(BytesIO(pdf)) as document:
        page = document.pages[0]
        layout = build_page_layout(page, 1)

    assert layout.page == 1
    assert layout.width > 0
    assert layout.height > 0
    assert layout.tokens
    for item in layout.tokens:
        x0, top, x1, bottom = layout.relative_box(item)
        assert 0.0 <= x0 <= x1 <= 1.0
        assert 0.0 <= top <= bottom <= 1.0


def test_tokens_keep_column_x_order():
    pdf = build_pdf(
        [("table", ["Nome", "Valore"], [["Alfa", "1.821,00"]], False)]
    )

    with pdfplumber.open(BytesIO(pdf)) as document:
        page = document.pages[0]
        layout = build_page_layout(page, 1)

    label = next(item for item in layout.tokens if item.text == "Alfa")
    value = next(item for item in layout.tokens if item.text == "1.821,00")

    assert label.x0 < value.x0
    assert label.page == value.page == 1


def test_group_rows_same_visual_line():
    rows = group_rows([tok("A", 10, 20, 100), tok("B", 30, 40, 100)])

    assert len(rows) == 1
    assert rows[0].text == "A B"


def test_group_rows_separate_lines():
    rows = group_rows([tok("A", 10, 20, 100), tok("B", 10, 20, 115)])

    assert len(rows) == 2
    assert [row.text for row in rows] == ["A", "B"]


def test_group_rows_close_but_distinct():
    rows = group_rows([tok("A", 10, 20, 100), tok("B", 10, 20, 104.6)])

    assert len(rows) == 2


def test_group_rows_tolerance_is_configurable():
    rows = group_rows([tok("A", 10, 20, 100), tok("B", 10, 20, 104.6)], tolerance=10.0)

    assert len(rows) == 1


def test_group_rows_populates_cells():
    rows = group_rows([tok("Label", 10, 50, 100), tok("1.821,00", 300, 340, 100)])

    assert len(rows) == 1
    assert [cell.text for cell in rows[0].cells] == ["Label", "1.821,00"]


def test_split_row_cells_by_horizontal_gap():
    cells = split_row_cells([tok("Label", 10, 50, 100), tok("1.821,00", 300, 340, 100)])

    assert [cell.text for cell in cells] == ["Label", "1.821,00"]
    assert cells[0].x0 == 10
    assert cells[1].x0 == 300


def test_split_row_cells_keeps_close_tokens_together():
    cells = split_row_cells(
        [tok("Netto", 10, 40, 100), tok("in", 42, 52, 100), tok("busta", 54, 84, 100)]
    )

    assert len(cells) == 1
    assert cells[0].text == "Netto in busta"


def test_reconstruct_line_text_pairs_label_and_value():
    tokens = [
        tok("Netto", 10, 40, 100),
        tok("in", 42, 52, 100),
        tok("busta", 54, 84, 100),
        tok("1.821,00", 300, 340, 100),
    ]

    assert reconstruct_line_text(tokens) == "Netto in busta: 1.821,00"


def test_reconstruct_line_text_keeps_prose():
    tokens = [tok("Testo", 10, 40, 100), tok("normale", 42, 80, 100)]

    assert reconstruct_line_text(tokens) == "Testo normale"


def test_reconstruct_line_text_does_not_pair_two_texts():
    tokens = [tok("Colonna", 10, 60, 100), tok("destra", 300, 350, 100)]

    assert reconstruct_line_text(tokens) == "Colonna  destra"


def test_reconstruct_line_text_does_not_pair_two_values():
    tokens = [tok("2.500,00", 10, 60, 100), tok("1.821,00", 300, 350, 100)]

    assert reconstruct_line_text(tokens) == "2.500,00  1.821,00"


def test_tokens_in_band_selects_overlapping_tokens():
    band = tokens_in_band([tok("A", 10, 20, 100), tok("B", 10, 20, 130)], 95, 112)

    assert [item.text for item in band] == ["A"]


def test_header_label_map_links_column_header_to_value():
    tokens = [
        tok("LORDO", 10, 50, 100),
        tok("NETTO IN BUSTA", 300, 380, 100),
        tok("2.500,00", 10, 60, 130),
        tok("1.821,00", 300, 350, 130),
    ]

    labels = header_label_map(tokens)
    value = next(item for item in tokens if item.text == "1.821,00")
    net = next(item for item in tokens if item.text == "2.500,00")

    assert labels[id(value)] == "NETTO IN BUSTA"
    assert labels[id(net)] == "LORDO"


def test_reconstruct_line_text_uses_column_labels():
    tokens = [tok("2.500,00", 10, 60, 130), tok("1.821,00", 300, 350, 130)]
    labels = {id(tokens[1]): "NETTO IN BUSTA"}

    assert (
        reconstruct_line_text(tokens, labels=labels)
        == "2.500,00  NETTO IN BUSTA: 1.821,00"
    )


def test_header_label_map_ignores_rows_without_header():
    tokens = [tok("1.821,00", 300, 350, 130), tok("2.500,00", 10, 60, 130)]

    assert header_label_map(tokens) == {}
