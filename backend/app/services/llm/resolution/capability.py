from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.services.llm.base import LLMProviderError
from app.services.llm.providers.ollama import OLLAMA_PROVIDER_NAME
from app.services.llm.providers.openai import EXTERNAL_API_PROVIDER_NAME

KNOWN_PROVIDER_IDS: tuple[str, ...] = (
    OLLAMA_PROVIDER_NAME,
    EXTERNAL_API_PROVIDER_NAME,
)


@dataclass(frozen=True)
class ProviderCapability:
    id: str
    enabled: bool
    models: tuple[str, ...] = ()


def provider_capabilities() -> tuple[ProviderCapability, ...]:
    """Globally available LLM providers.

    Ollama is always available. ``external_api`` is only globally available when
    the deployment enables it (``EXTERNAL_API_ENABLED``); a workspace must also allow
    it and provide its base URL, model and key.
    """
    settings = get_settings()
    return (
        ProviderCapability(
            id=OLLAMA_PROVIDER_NAME,
            enabled=True,
            models=(settings.ollama_default_model,),
        ),
        ProviderCapability(
            id=EXTERNAL_API_PROVIDER_NAME,
            enabled=settings.external_api_enabled,
            models=(),
        ),
    )


def known_provider_ids() -> tuple[str, ...]:
    return KNOWN_PROVIDER_IDS


def get_provider_capability(provider_id: str) -> ProviderCapability | None:
    for capability in provider_capabilities():
        if capability.id == provider_id:
            return capability
    return None


def is_provider_available(provider_id: str) -> bool:
    capability = get_provider_capability(provider_id)
    return capability is not None and capability.enabled


def default_provider_id() -> str:
    provider_id = get_settings().llm_default_provider
    if not is_provider_available(provider_id):
        raise LLMProviderError(
            "PROVIDER_NOT_AVAILABLE",
            f"Default provider '{provider_id}' is not available",
        )
    return provider_id
