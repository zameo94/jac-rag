import pytest

from app.core.config import get_settings
from app.services.llm import (
    EXTERNAL_API_PROVIDER_NAME,
    OLLAMA_PROVIDER_NAME,
    LLMProviderError,
    default_provider_id,
    get_provider_capability,
    is_provider_available,
    known_provider_ids,
    provider_capabilities,
)


def test_known_providers_are_ollama_and_external_api():
    assert known_provider_ids() == (OLLAMA_PROVIDER_NAME, EXTERNAL_API_PROVIDER_NAME)


def test_ollama_is_enabled_with_configured_model():
    settings = get_settings()

    capability = get_provider_capability(OLLAMA_PROVIDER_NAME)

    assert capability is not None
    assert capability.enabled is True
    assert capability.models == (settings.ollama_default_model,)
    assert is_provider_available(OLLAMA_PROVIDER_NAME) is True


def test_external_api_is_known_but_disabled():
    capability = get_provider_capability(EXTERNAL_API_PROVIDER_NAME)

    assert capability is not None
    assert capability.enabled is False
    assert capability.models == ()
    assert is_provider_available(EXTERNAL_API_PROVIDER_NAME) is False


def test_unknown_provider_is_not_available():
    assert get_provider_capability("does-not-exist") is None
    assert is_provider_available("does-not-exist") is False


def test_provider_capabilities_order_and_flags():
    providers = provider_capabilities()

    assert [provider.id for provider in providers] == [
        OLLAMA_PROVIDER_NAME,
        EXTERNAL_API_PROVIDER_NAME,
    ]
    assert [provider.enabled for provider in providers] == [True, False]


def test_default_provider_resolves_to_ollama():
    assert default_provider_id() == OLLAMA_PROVIDER_NAME


def test_default_provider_must_be_available(monkeypatch):
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", EXTERNAL_API_PROVIDER_NAME)
    get_settings.cache_clear()

    with pytest.raises(LLMProviderError) as error:
        default_provider_id()

    assert error.value.code == "PROVIDER_NOT_AVAILABLE"
