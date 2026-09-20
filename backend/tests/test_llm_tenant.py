import pytest

from app.models import Setting, Tenant
from app.schemas.setting import SettingScope
from app.services.llm import EXTERNAL_API_PROVIDER_NAME, OLLAMA_PROVIDER_NAME
from app.services.llm.tenant import (
    ALLOWED_PROVIDERS_KEY,
    DEFAULT_ALLOWED_PROVIDERS,
    LLM_SETTING_TYPE,
    MODEL_KEY,
    available_providers_for_tenant,
    normalize_allowed_providers,
    tenant_allowed_provider_ids,
    tenant_model_override,
)


async def create_tenant(session_factory, slug: str = "acme") -> int:
    async with session_factory() as session:
        tenant = Tenant(name="Acme", slug=slug)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        return tenant.id


def tenant_llm_setting(tenant_id: int, key: str, value) -> Setting:
    return Setting(
        scope_type=SettingScope.TENANT,
        scope_id=tenant_id,
        type=LLM_SETTING_TYPE,
        key=key,
        value=value,
    )


def test_normalize_allowed_providers_defaults():
    assert normalize_allowed_providers(None) == DEFAULT_ALLOWED_PROVIDERS
    assert normalize_allowed_providers([]) == DEFAULT_ALLOWED_PROVIDERS


def test_normalize_allowed_providers_normalizes_and_deduplicates():
    assert normalize_allowed_providers(
        [" OLLAMA ", "ollama", "external_api"]
    ) == (OLLAMA_PROVIDER_NAME, EXTERNAL_API_PROVIDER_NAME)


def test_normalize_allowed_providers_accepts_single_string():
    assert normalize_allowed_providers("ollama") == (OLLAMA_PROVIDER_NAME,)


def test_normalize_allowed_providers_rejects_unknown():
    with pytest.raises(ValueError):
        normalize_allowed_providers(["not-a-provider"])


async def test_available_providers_default_when_no_settings(session_factory):
    tenant_id = await create_tenant(session_factory)

    async with session_factory() as session:
        providers = await available_providers_for_tenant(session, tenant_id)

    assert [provider.id for provider in providers] == [OLLAMA_PROVIDER_NAME]
    assert providers[0].models


async def test_external_api_never_available_even_if_allowed(session_factory):
    tenant_id = await create_tenant(session_factory)

    async with session_factory() as session:
        session.add(
            tenant_llm_setting(
                tenant_id,
                ALLOWED_PROVIDERS_KEY,
                [OLLAMA_PROVIDER_NAME, EXTERNAL_API_PROVIDER_NAME],
            )
        )
        await session.commit()

    async with session_factory() as session:
        providers = await available_providers_for_tenant(session, tenant_id)

    assert [provider.id for provider in providers] == [OLLAMA_PROVIDER_NAME]


async def test_tenant_allowing_only_external_gets_no_providers(session_factory):
    tenant_id = await create_tenant(session_factory)

    async with session_factory() as session:
        session.add(
            tenant_llm_setting(
                tenant_id, ALLOWED_PROVIDERS_KEY, [EXTERNAL_API_PROVIDER_NAME]
            )
        )
        await session.commit()

    async with session_factory() as session:
        providers = await available_providers_for_tenant(session, tenant_id)

    assert providers == ()


async def test_user_scope_setting_does_not_affect_tenant(session_factory):
    tenant_id = await create_tenant(session_factory)

    async with session_factory() as session:
        session.add(
            Setting(
                scope_type=SettingScope.USER,
                scope_id=tenant_id,
                type=LLM_SETTING_TYPE,
                key=ALLOWED_PROVIDERS_KEY,
                value=[EXTERNAL_API_PROVIDER_NAME],
            )
        )
        await session.commit()

    async with session_factory() as session:
        providers = await available_providers_for_tenant(session, tenant_id)

    assert [provider.id for provider in providers] == [OLLAMA_PROVIDER_NAME]


async def test_tenant_allowed_provider_ids_from_settings(session_factory):
    tenant_id = await create_tenant(session_factory)

    async with session_factory() as session:
        session.add(
            tenant_llm_setting(tenant_id, ALLOWED_PROVIDERS_KEY, [OLLAMA_PROVIDER_NAME])
        )
        await session.commit()

    async with session_factory() as session:
        assert await tenant_allowed_provider_ids(session, tenant_id) == (
            OLLAMA_PROVIDER_NAME,
        )


async def test_tenant_model_override(session_factory):
    tenant_id = await create_tenant(session_factory)

    async with session_factory() as session:
        assert await tenant_model_override(session, tenant_id) is None
        session.add(tenant_llm_setting(tenant_id, MODEL_KEY, "llama3.1"))
        await session.commit()

    async with session_factory() as session:
        assert await tenant_model_override(session, tenant_id) == "llama3.1"
