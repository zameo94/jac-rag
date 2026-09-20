from __future__ import annotations

from app.core.config import get_settings
from app.services.llm.base import LLMProvider, LLMProviderError
from app.services.llm.ollama import OLLAMA_PROVIDER_NAME, OllamaProvider


def resolve_model(provider_id: str, override: str | None = None) -> str:
    if provider_id == OLLAMA_PROVIDER_NAME:
        settings = get_settings()
        candidate = (override or "").strip()
        return candidate or settings.ollama_default_model
    raise LLMProviderError(
        "PROVIDER_NOT_IMPLEMENTED", f"Provider '{provider_id}' is not implemented"
    )


def create_provider(provider_id: str, *, model: str | None = None) -> LLMProvider:
    """Instantiate the single selected provider. No external providers yet."""
    settings = get_settings()
    if provider_id == OLLAMA_PROVIDER_NAME:
        return OllamaProvider(
            settings.ollama_base_url, resolve_model(provider_id, model)
        )
    raise LLMProviderError(
        "PROVIDER_NOT_IMPLEMENTED", f"Provider '{provider_id}' is not implemented"
    )
