from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.services.llm.base import LLMProvider, LLMProviderError
from app.services.llm.resolution.external import external_config
from app.services.llm.providers.ollama import OLLAMA_PROVIDER_NAME, OllamaProvider
from app.services.llm.providers.openai import EXTERNAL_API_PROVIDER_NAME, OpenAIProvider


def resolve_model(provider_id: str, override: str | None = None) -> str:
    if provider_id == OLLAMA_PROVIDER_NAME:
        settings = get_settings()
        candidate = (override or "").strip()
        return candidate or settings.ollama_default_model
    raise LLMProviderError(
        "PROVIDER_NOT_IMPLEMENTED", f"Provider '{provider_id}' has no local model"
    )


def create_provider(provider_id: str, *, model: str | None = None) -> LLMProvider:
    """Create a provider that needs no per-tenant configuration (Ollama)."""
    settings = get_settings()
    if provider_id == OLLAMA_PROVIDER_NAME:
        return OllamaProvider(
            settings.ollama_base_url, resolve_model(provider_id, model)
        )
    raise LLMProviderError(
        "PROVIDER_NOT_CONFIGURED",
        f"Provider '{provider_id}' requires tenant configuration",
    )


async def build_provider(
    session: AsyncSession,
    tenant_id: int,
    provider_id: str,
    model: str | None = None,
) -> tuple[LLMProvider, str]:
    """Build the single provider for a request plus its resolved model name."""
    if provider_id == OLLAMA_PROVIDER_NAME:
        settings = get_settings()
        resolved = resolve_model(provider_id, model)
        return OllamaProvider(settings.ollama_base_url, resolved), resolved

    if provider_id == EXTERNAL_API_PROVIDER_NAME:
        config = await external_config(session, tenant_id)
        if config is None:
            raise LLMProviderError(
                "PROVIDER_NOT_CONFIGURED",
                "External LLM is not configured for this tenant",
            )
        return OpenAIProvider(config.base_url, config.api_key, config.model), config.model

    raise LLMProviderError(
        "PROVIDER_NOT_IMPLEMENTED", f"Provider '{provider_id}' is not implemented"
    )
