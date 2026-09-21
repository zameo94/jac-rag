from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.setting import SettingScope
from app.services.llm.resolution.capability import (
    KNOWN_PROVIDER_IDS,
    ProviderCapability,
    provider_capabilities,
)
from app.services.llm.providers.ollama import OLLAMA_PROVIDER_NAME
from app.services.settings import get_value

DEFAULT_ALLOWED_PROVIDERS: tuple[str, ...] = (OLLAMA_PROVIDER_NAME,)
LLM_SETTING_TYPE = "llm"
ALLOWED_PROVIDERS_KEY = "allowed_providers"
MODEL_KEY = "model"
DEFAULT_PROVIDER_KEY = "default_provider"


def normalize_allowed_providers(value) -> tuple[str, ...]:
    if value is None or value == []:
        return DEFAULT_ALLOWED_PROVIDERS
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise ValueError("allowed_providers must be a list of provider ids")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("provider ids must be strings")
        provider = item.strip().lower()
        if provider not in KNOWN_PROVIDER_IDS:
            raise ValueError(f"Unknown provider: {item}")
        if provider not in normalized:
            normalized.append(provider)

    if not normalized:
        return DEFAULT_ALLOWED_PROVIDERS
    return tuple(normalized)


async def tenant_allowed_provider_ids(
    session: AsyncSession, tenant_id: int
) -> tuple[str, ...]:
    value = await get_value(
        session,
        SettingScope.TENANT,
        tenant_id,
        LLM_SETTING_TYPE,
        ALLOWED_PROVIDERS_KEY,
    )
    return normalize_allowed_providers(value)


async def tenant_model_override(
    session: AsyncSession, tenant_id: int
) -> str | None:
    value = await get_value(
        session,
        SettingScope.TENANT,
        tenant_id,
        LLM_SETTING_TYPE,
        MODEL_KEY,
    )
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


async def tenant_default_provider(
    session: AsyncSession, tenant_id: int
) -> str | None:
    value = await get_value(
        session,
        SettingScope.TENANT,
        tenant_id,
        LLM_SETTING_TYPE,
        DEFAULT_PROVIDER_KEY,
    )
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return None


async def available_providers_for_tenant(
    session: AsyncSession, tenant_id: int
) -> tuple[ProviderCapability, ...]:
    """Providers a tenant may use: its allowed set filtered by global capability.

    A tenant can only allow known providers, and a provider globally disabled
    (e.g. external APIs for now) is never returned even if listed.
    """
    allowed = set(await tenant_allowed_provider_ids(session, tenant_id))
    return tuple(
        capability
        for capability in provider_capabilities()
        if capability.enabled and capability.id in allowed
    )
