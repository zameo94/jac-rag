"""Feature-flagged OCR used to recover text the PDF text layer misses.

Design rules (deterministic, no LLM):

* the text layer always wins; OCR never overrides a text-layer number;
* OCR is used only when needed:
  - the page text layer is too sparse -> full-page OCR;
  - the page is image-dominant but has a text layer -> OCR only *labels*
    (alphabetic tokens), so values stay authoritative;
* OCR is never run on ordinary text PDFs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Protocol, Sequence

from app.core.config import get_settings
from app.services.rag.parsers.pdf_layout import PageLayout, PdfToken

logger = logging.getLogger(__name__)

LOCALE_TO_TESSERACT = {"it": "ita", "en": "eng"}
DEFAULT_OCR_LANGUAGE = "eng"
POINTS_PER_INCH = 72.0


@dataclass(frozen=True)
class OcrToken:
    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    confidence: float


class OcrEngine(Protocol):
    def recognize(self, image, *, languages: str) -> list[OcrToken]:
        ...


class TesseractOcrEngine:
    def __init__(self, *, min_confidence: float) -> None:
        self._min_confidence = min_confidence

    def recognize(self, image, *, languages: str) -> list[OcrToken]:
        import pytesseract
        from pytesseract import Output

        data = pytesseract.image_to_data(image, lang=languages, output_type=Output.DICT)
        tokens: list[OcrToken] = []
        for index, raw_text in enumerate(data.get("text", [])):
            text = (raw_text or "").strip()
            if not text:
                continue
            try:
                confidence = float(data["conf"][index]) / 100.0
            except (TypeError, ValueError):
                continue
            if confidence < 0 or confidence < self._min_confidence:
                continue
            left = float(data["left"][index])
            top = float(data["top"][index])
            width = float(data["width"][index])
            height = float(data["height"][index])
            tokens.append(
                OcrToken(
                    text=text,
                    x0=left,
                    top=top,
                    x1=left + width,
                    bottom=top + height,
                    confidence=confidence,
                )
            )
        return tokens


def tesseract_language(locale: str | None) -> str:
    if not locale:
        return DEFAULT_OCR_LANGUAGE
    return LOCALE_TO_TESSERACT.get(locale.strip().lower(), DEFAULT_OCR_LANGUAGE)


def ocr_languages(locales: Sequence[str] | None) -> str:
    if not locales:
        return DEFAULT_OCR_LANGUAGE
    mapped = []
    for locale in locales:
        language = tesseract_language(locale)
        if language not in mapped:
            mapped.append(language)
    return "+".join(mapped) if mapped else DEFAULT_OCR_LANGUAGE


def get_ocr_engine() -> OcrEngine | None:
    settings = get_settings()
    if not settings.ocr_enabled:
        return None
    return TesseractOcrEngine(min_confidence=settings.ocr_min_confidence)


class PdfPageRenderer:
    def __init__(self, content: bytes) -> None:
        import pypdfium2 as pdfium

        self._document = pdfium.PdfDocument(content)

    def render(self, page_index: int, dpi: int):
        page = self._document[page_index]
        return page.render(scale=dpi / POINTS_PER_INCH).to_pil()

    def close(self) -> None:
        self._document.close()


@dataclass
class OcrContext:
    engine: OcrEngine
    renderer: PdfPageRenderer
    languages: str
    dpi: int
    min_text_chars: int
    image_dominance_ratio: float


def image_area_ratio(page) -> float:
    width = float(page.width or 0.0)
    height = float(page.height or 0.0)
    page_area = width * height
    if page_area <= 0:
        return 0.0
    largest = 0.0
    for image in page.images or []:
        image_area = float(image.get("width") or 0.0) * float(image.get("height") or 0.0)
        largest = max(largest, image_area)
    return min(largest / page_area, 1.0)


def _normalize(text: str) -> str:
    return "".join(character.lower() for character in text if character.isalnum())


def _overlaps(token: PdfToken, x0: float, top: float, x1: float, bottom: float) -> bool:
    return token.x0 < x1 and token.x1 > x0 and token.top < bottom and token.bottom > top


def _merge_tokens(
    text_tokens: tuple[PdfToken, ...],
    ocr_tokens: list[OcrToken],
    *,
    page: int,
    dpi: int,
    labels_only: bool,
) -> list[PdfToken]:
    scale = POINTS_PER_INCH / dpi
    merged: list[PdfToken] = []
    for token in ocr_tokens:
        if labels_only and any(character.isdigit() for character in token.text):
            continue
        normalized = _normalize(token.text)
        if not normalized:
            continue
        x0, top = token.x0 * scale, token.top * scale
        x1, bottom = token.x1 * scale, token.bottom * scale
        if any(
            _normalize(existing.text) == normalized
            and _overlaps(existing, x0, top, x1, bottom)
            for existing in text_tokens
        ):
            continue
        merged.append(
            PdfToken(
                text=token.text,
                page=page,
                x0=x0,
                x1=x1,
                top=top,
                bottom=bottom,
                size=0.0,
                source="ocr",
            )
        )
    return merged


def augment_layout(layout: PageLayout, page, context: OcrContext) -> PageLayout:
    text_chars = sum(len(token.text) for token in layout.tokens)
    if text_chars < context.min_text_chars:
        labels_only = False
    elif image_area_ratio(page) >= context.image_dominance_ratio:
        labels_only = True
    else:
        return layout

    image = context.renderer.render(layout.page - 1, context.dpi)
    ocr_tokens = context.engine.recognize(image, languages=context.languages)
    merged = _merge_tokens(
        layout.tokens,
        ocr_tokens,
        page=layout.page,
        dpi=context.dpi,
        labels_only=labels_only,
    )
    if not merged:
        return layout
    return replace(layout, tokens=layout.tokens + tuple(merged))
