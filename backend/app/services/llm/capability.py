from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.services.llm.base import LLMProviderError
from app.services.llm.ollama import OLLAMA_PROVIDER_NAME

EXTERNAL_API_PROVIDER_NAME = "external_api"


@dataclass(frozen=True)
class ProviderCapability:
    id: str
    enabled: bool
    models: tuple[str, ...] = ()


def provider_capabilities() -> tuple[ProviderCapability, ...]:
    """Globally available LLM providers.

    Only Ollama is implemented and enabled. ``external_api`` is represented as a
    known but disabled capability: it is intentionally not configurable yet, so a
    non-implemented external provider can never be selected.
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
            enabled=False,
            models=(),
        ),
    )


def known_provider_ids() -> tuple[str, ...]:
    return tuple(capability.id for capability in provider_capabilities())


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
