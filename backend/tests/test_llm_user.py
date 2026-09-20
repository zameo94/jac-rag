import pytest

from app.models import Setting, Tenant
from app.schemas.setting import SettingScope
from app.services.llm import (
    EXTERNAL_API_PROVIDER_NAME,
    OLLAMA_PROVIDER_NAME,
    LLMProviderError,
    ProviderCapability,
)
from app.services.llm.defaults import (
    GLOBAL_DEFAULT_PROVIDER_KEY,
    global_default_provider,
)
from app.services.llm.tenant import (
    ALLOWED_PROVIDERS_KEY,
    DEFAULT_PROVIDER_KEY,
    LLM_SETTING_TYPE,
)
from app.services.llm.user import (
    SELECTED_PROVIDER_KEY,
    resolve_user_provider,
    set_user_provider,
    user_selected_provider,
)

OTHER_PROVIDER = "other"


async def create_tenant(session_factory, slug: str = "acme") -> int:
    async with session_factory() as session:
        tenant = Tenant(name="Acme", slug=slug)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        return tenant.id


async def store_setting(session_factory, scope_type, scope_id, key, value) -> None:
    async with session_factory() as session:
        session.add(
            Setting(
                scope_type=scope_type,
                scope_id=scope_id,
                type=LLM_SETTING_TYPE,
                key=key,
                value=value,
            )
        )
        await session.commit()


async def store_user_provider(session_factory, user_id: int, provider_id: str) -> None:
    await store_setting(
        session_factory, SettingScope.USER, user_id, SELECTED_PROVIDER_KEY, provider_id
    )


async def store_tenant_allowed(session_factory, tenant_id: int, providers) -> None:
    await store_setting(
        session_factory, SettingScope.TENANT, tenant_id, ALLOWED_PROVIDERS_KEY, providers
    )


async def store_tenant_default(session_factory, tenant_id: int, provider_id: str) -> None:
    await store_setting(
        session_factory, SettingScope.TENANT, tenant_id, DEFAULT_PROVIDER_KEY, provider_id
    )


async def store_global_default(session_factory, provider_id: str) -> None:
    await store_setting(
        session_factory, SettingScope.GLOBAL, None, GLOBAL_DEFAULT_PROVIDER_KEY, provider_id
    )


def capability(provider_id: str) -> ProviderCapability:
    return ProviderCapability(id=provider_id, enabled=True, models=("m",))


async def two_available(session, tenant_id):
    return (capability(OLLAMA_PROVIDER_NAME), capability(OTHER_PROVIDER))


async def returns_external(session):
    return EXTERNAL_API_PROVIDER_NAME


async def returns_none(session):
    return None


async def test_resolve_defaults_to_ollama_when_not_selected(session_factory):
    tenant_id = await create_tenant(session_factory)

    async with session_factory() as session:
        provider = await resolve_user_provider(session, tenant_id, user_id=42)

    assert provider.id == OLLAMA_PROVIDER_NAME


async def test_set_and_resolve_user_provider(session_factory):
    tenant_id = await create_tenant(session_factory)

    async with session_factory() as session:
        selected = await set_user_provider(session, tenant_id, 42, OLLAMA_PROVIDER_NAME)
        await session.commit()

    assert selected == OLLAMA_PROVIDER_NAME
    async with session_factory() as session:
        assert await user_selected_provider(session, 42) == OLLAMA_PROVIDER_NAME
        provider = await resolve_user_provider(session, tenant_id, 42)

    assert provider.id == OLLAMA_PROVIDER_NAME


async def test_set_user_provider_normalizes_input(session_factory):
    tenant_id = await create_tenant(session_factory)

    async with session_factory() as session:
        assert (
            await set_user_provider(session, tenant_id, 42, "  OLLAMA ")
            == OLLAMA_PROVIDER_NAME
        )
        await session.commit()


async def test_set_user_provider_rejects_disabled_external(session_factory):
    tenant_id = await create_tenant(session_factory)

    async with session_factory() as session:
        with pytest.raises(LLMProviderError) as error:
            await set_user_provider(
                session, tenant_id, 42, EXTERNAL_API_PROVIDER_NAME
            )

    assert error.value.code == "PROVIDER_NOT_AVAILABLE"


async def test_set_user_provider_rejects_unknown(session_factory):
    tenant_id = await create_tenant(session_factory)

    async with session_factory() as session:
        with pytest.raises(LLMProviderError) as error:
            await set_user_provider(session, tenant_id, 42, "not-a-provider")

    assert error.value.code == "PROVIDER_NOT_AVAILABLE"


async def test_set_rejects_provider_not_allowed_by_tenant(session_factory):
    tenant_id = await create_tenant(session_factory)
    await store_tenant_allowed(session_factory, tenant_id, [EXTERNAL_API_PROVIDER_NAME])

    async with session_factory() as session:
        with pytest.raises(LLMProviderError) as error:
            await set_user_provider(session, tenant_id, 42, OLLAMA_PROVIDER_NAME)

    assert error.value.code == "PROVIDER_NOT_AVAILABLE"


async def test_resolve_rejects_selection_not_allowed_by_tenant(session_factory):
    tenant_id = await create_tenant(session_factory)
    await store_user_provider(session_factory, 42, EXTERNAL_API_PROVIDER_NAME)

    async with session_factory() as session:
        with pytest.raises(LLMProviderError) as error:
            await resolve_user_provider(session, tenant_id, 42)

    assert error.value.code == "PROVIDER_NOT_AVAILABLE"


async def test_resolve_no_provider_available(session_factory):
    tenant_id = await create_tenant(session_factory)
    await store_tenant_allowed(session_factory, tenant_id, [EXTERNAL_API_PROVIDER_NAME])

    async with session_factory() as session:
        with pytest.raises(LLMProviderError) as error:
            await resolve_user_provider(session, tenant_id, 42)

    assert error.value.code == "NO_PROVIDER_AVAILABLE"


async def test_global_default_provider_uses_setting(session_factory):
    await store_global_default(session_factory, OTHER_PROVIDER)

    async with session_factory() as session:
        assert await global_default_provider(session) == OTHER_PROVIDER


async def test_global_default_provider_falls_back_to_env(session_factory):
    async with session_factory() as session:
        assert await global_default_provider(session) == OLLAMA_PROVIDER_NAME


async def test_resolve_uses_global_default_when_no_user_or_tenant_choice(
    session_factory,
):
    tenant_id = await create_tenant(session_factory)
    await store_global_default(session_factory, OLLAMA_PROVIDER_NAME)

    async with session_factory() as session:
        provider = await resolve_user_provider(session, tenant_id, 42)

    assert provider.id == OLLAMA_PROVIDER_NAME


async def test_user_selection_prevails_over_global_default(
    session_factory, monkeypatch
):
    tenant_id = await create_tenant(session_factory)
    monkeypatch.setattr(
        "app.services.llm.user.available_providers_for_tenant", two_available
    )
    await store_user_provider(session_factory, 42, OLLAMA_PROVIDER_NAME)
    await store_global_default(session_factory, OTHER_PROVIDER)

    async with session_factory() as session:
        provider = await resolve_user_provider(session, tenant_id, 42)

    assert provider.id == OLLAMA_PROVIDER_NAME


async def test_tenant_default_prevails_over_global_default(
    session_factory, monkeypatch
):
    tenant_id = await create_tenant(session_factory)
    monkeypatch.setattr(
        "app.services.llm.user.available_providers_for_tenant", two_available
    )
    await store_tenant_default(session_factory, tenant_id, OLLAMA_PROVIDER_NAME)
    await store_global_default(session_factory, OTHER_PROVIDER)

    async with session_factory() as session:
        provider = await resolve_user_provider(session, tenant_id, 42)

    assert provider.id == OLLAMA_PROVIDER_NAME


async def test_global_default_not_used_when_tenant_disallows(session_factory):
    tenant_id = await create_tenant(session_factory)
    await store_global_default(session_factory, OLLAMA_PROVIDER_NAME)
    await store_tenant_allowed(session_factory, tenant_id, [EXTERNAL_API_PROVIDER_NAME])

    async with session_factory() as session:
        with pytest.raises(LLMProviderError) as error:
            await resolve_user_provider(session, tenant_id, 42)

    assert error.value.code == "NO_PROVIDER_AVAILABLE"


async def test_resolve_uses_only_available_when_default_unavailable(
    session_factory, monkeypatch
):
    tenant_id = await create_tenant(session_factory)
    monkeypatch.setattr(
        "app.services.llm.user.global_default_provider", returns_external
    )

    async with session_factory() as session:
        provider = await resolve_user_provider(session, tenant_id, 42)

    assert provider.id == OLLAMA_PROVIDER_NAME


async def test_error_when_multiple_available_and_no_default_matches(
    session_factory, monkeypatch
):
    tenant_id = await create_tenant(session_factory)
    monkeypatch.setattr(
        "app.services.llm.user.available_providers_for_tenant", two_available
    )
    monkeypatch.setattr("app.services.llm.user.global_default_provider", returns_none)

    async with session_factory() as session:
        with pytest.raises(LLMProviderError) as error:
            await resolve_user_provider(session, tenant_id, 42)

    assert error.value.code == "PROVIDER_NOT_SELECTED"
