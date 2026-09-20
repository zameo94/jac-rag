from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field


@dataclass
class ExtractionDiagnostics:
    pages: int = 0
    text_blocks: int = 0
    headings: int = 0
    list_items: int = 0
    tables_detected: int = 0
    rows_detected: int = 0
    cells_detected: int = 0
    figures: int = 0
    fallback_blocks: int = 0
    repeated_layout_blocks: int = 0
    oversized_blocks: int = 0
    suspicious_tables: int = 0
    warnings: list[str] = field(default_factory=list)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def log(self, logger: logging.Logger, *, source: str | None = None) -> None:
        logger.debug("extraction diagnostics source=%s %s", source, self.as_dict())
