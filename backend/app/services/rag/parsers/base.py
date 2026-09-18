from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    page_count: int

    @property
    def chars_per_page(self) -> float:
        if self.page_count <= 0:
            return float(len(self.text))
        return len(self.text) / self.page_count

    def has_text_layer(self) -> bool:
        return self.chars_per_page >= get_settings().min_chars_per_page
