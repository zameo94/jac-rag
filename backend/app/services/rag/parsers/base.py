from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from app.services.rag.ir import Document


class DocumentParser(ABC):
    """Format-specific parser producing the Common Document IR.

    New formats only need to subclass this and register their ``mime_types``.
    """

    mime_types: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def parse(self, content: bytes, *, source: str | None = None) -> Document:
        raise NotImplementedError

    def __call__(self, content: bytes) -> Document:
        return self.parse(content)
