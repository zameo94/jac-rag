from io import BytesIO

import pdfplumber
import pytest

from app.core.config import get_settings
from app.services.rag.parsers import parse_pdf
from app.services.rag.parsers import ocr as ocr_module
from app.services.rag.parsers.ocr import (
    OcrToken,
    ocr_languages,
    tesseract_language,
)
from app.services.rag.parsers.pdf_layout import build_page_layout
from tests.fixtures import make_positioned_pdf

DPI = 200
SCALE = 72.0 / DPI


class FakeOcrEngine:
    def __init__(self, tokens: list[OcrToken]) -> None:
        self.tokens = tokens
        self.calls: list[str] = []

    def recognize(self, image, *, languages: str) -> list[OcrToken]:
        self.calls.append(languages)
        return self.tokens


def enable_ocr(monkeypatch, engine: FakeOcrEngine, *, image_dominance: float = 1.0) -> int:
    monkeypatch.setenv("OCR_ENABLED", "true")
    monkeypatch.setenv("OCR_DPI", str(DPI))
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.services.rag.parsers.pdf.get_ocr_engine", lambda: engine
    )
    monkeypatch.setattr(ocr_module, "image_area_ratio", lambda page: image_dominance)
    return DPI


def value_token_position(pdf: bytes):
    with pdfplumber.open(BytesIO(pdf)) as document:
        layout = build_page_layout(document.pages[0], 1)
    return next(token for token in layout.tokens if token.text == "1.821,00")


def label_token_for(value, text: str) -> OcrToken:
    x0 = (value.x0 - 160) / SCALE
    x1 = (value.x0 - 20) / SCALE
    return OcrToken(
        text=text,
        x0=x0,
        top=value.top / SCALE,
        x1=x1,
        bottom=value.bottom / SCALE,
        confidence=0.95,
    )


def test_language_mapping():
    assert tesseract_language("it") == "ita"
    assert tesseract_language("en") == "eng"
    assert tesseract_language(None) == "eng"
    assert ocr_languages(["it"]) == "ita"
    assert ocr_languages(["it", "en"]) == "ita+eng"
    assert ocr_languages(None) == "eng"


def test_ocr_disabled_by_default_does_not_run(monkeypatch):
    engine = FakeOcrEngine([])
    monkeypatch.setattr("app.services.rag.parsers.pdf.get_ocr_engine", lambda: engine)

    document = parse_pdf(make_positioned_pdf([(72, 700, "Testo normale senza OCR")]))

    assert engine.calls == []
    assert "Netto" not in document.text


def test_label_ocr_recovers_missing_label(monkeypatch):
    pdf = make_positioned_pdf(
        [
            (72, 740, "Contenuto del cedolino di prova completo"),
            (300, 700, "1.821,00"),
        ]
    )
    value = value_token_position(pdf)
    engine = FakeOcrEngine([label_token_for(value, "Netto in busta")])
    enable_ocr(monkeypatch, engine)

    document = parse_pdf(pdf, languages=["it"])

    assert "Netto in busta: 1.821,00" in document.text
    assert engine.calls == ["ita"]


def test_label_ocr_never_adds_numbers(monkeypatch):
    pdf = make_positioned_pdf(
        [
            (72, 740, "Contenuto del cedolino di prova completo"),
            (300, 700, "1.821,00"),
        ]
    )
    value = value_token_position(pdf)
    engine = FakeOcrEngine(
        [
            label_token_for(value, "Netto in busta"),
            label_token_for(value, "999,99"),
        ]
    )
    enable_ocr(monkeypatch, engine)

    document = parse_pdf(pdf, languages=["it"])

    assert "999,99" not in document.text
    assert "Netto in busta: 1.821,00" in document.text


def test_full_page_ocr_when_text_layer_sparse(monkeypatch):
    engine = FakeOcrEngine(
        [
            OcrToken(
                text="Scansione",
                x0=100,
                top=100,
                x1=200,
                bottom=130,
                confidence=0.9,
            )
        ]
    )
    monkeypatch.setenv("OCR_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.rag.parsers.pdf.get_ocr_engine", lambda: engine)
    monkeypatch.setattr(ocr_module, "image_area_ratio", lambda page: 0.0)

    pdf = make_positioned_pdf([])

    document = parse_pdf(pdf, languages=["en"])

    assert "Scansione" in document.text
    assert engine.calls == ["eng"]


def test_no_ocr_on_plain_text_pdf(monkeypatch):
    engine = FakeOcrEngine([OcrToken("X", 0, 0, 1, 1, 0.9)])
    monkeypatch.setenv("OCR_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.rag.parsers.pdf.get_ocr_engine", lambda: engine)
    monkeypatch.setattr(ocr_module, "image_area_ratio", lambda page: 0.0)

    pdf = make_positioned_pdf(
        [(72, 700, "Questo e un normale paragrafo di testo con molte lettere.")]
    )

    document = parse_pdf(pdf)

    assert engine.calls == []
    assert "Questo e un normale paragrafo" in document.text


def test_ocr_only_row_is_emitted(monkeypatch):
    pdf = make_positioned_pdf(
        [
            (72, 740, "Contenuto del cedolino di prova completo"),
            (300, 700, "1.821,00"),
        ]
    )
    with pdfplumber.open(BytesIO(pdf)) as document:
        layout = build_page_layout(document.pages[0], 1)
    value = next(token for token in layout.tokens if token.text == "1.821,00")
    label_top = value.top - 40
    engine = FakeOcrEngine(
        [
            OcrToken(
                text="Netto in busta",
                x0=60 / SCALE,
                top=label_top / SCALE,
                x1=200 / SCALE,
                bottom=(label_top + 9) / SCALE,
                confidence=0.95,
            )
        ]
    )
    enable_ocr(monkeypatch, engine)

    document = parse_pdf(pdf, languages=["it"])

    assert "Netto in busta" in document.text
