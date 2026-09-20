from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.setting import SettingScope
from app.services.llm.base import LLMProviderError
from app.services.llm.capability import ProviderCapability
from app.services.llm.defaults import global_default_provider
from app.services.llm.tenant import (
    LLM_SETTING_TYPE,
    available_providers_for_tenant,
    tenant_default_provider,
)
from app.services.settings import get_value, set_value

SELECTED_PROVIDER_KEY = "selected_provider"


async def user_selected_provider(
    session: AsyncSession, user_id: int
) -> str | None:
    value = await get_value(
        session,
        SettingScope.USER,
        user_id,
        LLM_SETTING_TYPE,
        SELECTED_PROVIDER_KEY,
    )
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return None


async def set_user_provider(
    session: AsyncSession, tenant_id: int, user_id: int, provider_id: str
) -> str:
    """Select the single provider for a user, rejecting any unavailable one."""
    available = {
        capability.id
        for capability in await available_providers_for_tenant(session, tenant_id)
    }
    normalized = provider_id.strip().lower()
    if normalized not in available:
        raise LLMProviderError(
            "PROVIDER_NOT_AVAILABLE",
            f"Provider '{provider_id}' is not available for this tenant",
        )
    await set_value(
        session,
        SettingScope.USER,
        user_id,
        LLM_SETTING_TYPE,
        SELECTED_PROVIDER_KEY,
        normalized,
    )
    return normalized


async def resolve_user_provider(
    session: AsyncSession, tenant_id: int, user_id: int
) -> ProviderCapability:
    """The single provider a user request must use.

    Priority: the user's explicit selection, then the tenant default, then the
    global default. Every candidate is filtered by the tenant's allowed
    providers and the global capability, so a global default can never bypass
    tenant policy. Exactly one provider is returned: there is no fallback, no
    parallel or multi-provider execution.
    """
    available = await available_providers_for_tenant(session, tenant_id)
    if not available:
        raise LLMProviderError(
            "NO_PROVIDER_AVAILABLE",
            "No LLM provider is available for this tenant",
        )
    by_id = {capability.id: capability for capability in available}

    selected = await user_selected_provider(session, user_id)
    if selected is not None:
        if selected not in by_id:
            raise LLMProviderError(
                "PROVIDER_NOT_AVAILABLE",
                f"Selected provider '{selected}' is not available for this tenant",
            )
        return by_id[selected]

    tenant_default = await tenant_default_provider(session, tenant_id)
    if tenant_default is not None and tenant_default in by_id:
        return by_id[tenant_default]

    global_default = await global_default_provider(session)
    if global_default is not None and global_default in by_id:
        return by_id[global_default]

    if len(available) == 1:
        return available[0]

    raise LLMProviderError(
        "PROVIDER_NOT_SELECTED",
        "No provider selected and no default is available",
    )
