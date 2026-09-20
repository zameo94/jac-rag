from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


class LLMRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class LLMMessage:
    role: LLMRole
    content: str


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    provider: str


class LLMProviderError(Exception):
    """Provider-agnostic failure, carrying a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LLMProvider(ABC):
    """Single LLM backend selected for one request.

    The chatbot depends on this contract only: it never imports a concrete
    provider. A request uses exactly one provider; no fallback, no parallel or
    multi-provider orchestration.
    """

    name: ClassVar[str] = ""

    @abstractmethod
    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        raise NotImplementedError

    @abstractmethod
    def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        raise NotImplementedError

    async def aclose(self) -> None:
        """Release provider resources. Stateless providers need not override."""
        return None
