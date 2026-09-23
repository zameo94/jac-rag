import json

import httpx
import pytest

from app.core.config import get_settings
from app.models import Membership, Workspace
from app.schemas.membership import MembershipRole
from app.schemas.setting import SettingScope
from app.services.crypto import CryptoError, decrypt, encrypt
from app.services.llm.base import LLMMessage, LLMProviderError, LLMRole
from app.services.llm.resolution.capability import is_provider_available
from app.services.llm.resolution.external import external_config, set_external_config
from app.services.llm.factory import build_provider
from app.services.llm.providers.openai import OpenAIProvider
from app.services.llm.resolution.workspace import LLM_SETTING_TYPE
from app.services.settings import get_value
from tests.helpers import register_and_login, user_id_for


def message(text: str = "hi") -> LLMMessage:
    return LLMMessage(role=LLMRole.USER, content=text)


async def create_workspace_row(session_factory, slug: str = "acme") -> int:
    async with session_factory() as session:
        workspace = Workspace(name="Acme", slug=slug)
        session.add(workspace)
        await session.commit()
        await session.refresh(workspace)
        return workspace.id


def make_provider(handler, model: str = "gpt-x") -> OpenAIProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenAIProvider("https://api.test/v1", "sk-test", model, client=client)


# --------------------------------------------------------------------------- #
# Crypto                                                                       #
# --------------------------------------------------------------------------- #


def test_crypto_roundtrip():
    token = encrypt("super-secret")

    assert token != "super-secret"
    assert decrypt(token) == "super-secret"


def test_crypto_invalid_token_raises():
    with pytest.raises(CryptoError):
        decrypt("not-a-token")


# --------------------------------------------------------------------------- #
# OpenAI-compatible provider                                                   #
# --------------------------------------------------------------------------- #


async def test_openai_generate_success():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"model": "gpt-x", "choices": [{"message": {"content": "Ciao"}}]},
        )

    result = await make_provider(handler).generate([message()])

    assert result.content == "Ciao"
    assert result.provider == "external_api"
    assert result.model == "gpt-x"
    assert captured["url"] == "https://api.test/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test"
    assert captured["payload"]["stream"] is False


async def test_openai_generate_model_override_and_temperature():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    await make_provider(handler).generate(
        [message()], model="other", temperature=0.7
    )

    assert captured["payload"]["model"] == "other"
    assert captured["payload"]["temperature"] == 0.7


async def test_openai_generate_http_error():
    provider = make_provider(lambda request: httpx.Response(401, text="bad key"))

    with pytest.raises(LLMProviderError) as error:
        await provider.generate([message()])

    assert error.value.code == "LLM_HTTP_ERROR"


async def test_openai_generate_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(LLMProviderError) as error:
        await make_provider(handler).generate([message()])

    assert error.value.code == "LLM_UNAVAILABLE"


async def test_openai_generate_invalid_json():
    provider = make_provider(lambda request: httpx.Response(200, text="not-json"))

    with pytest.raises(LLMProviderError) as error:
        await provider.generate([message()])

    assert error.value.code == "LLM_INVALID_RESPONSE"


async def test_openai_generate_error_field():
    provider = make_provider(
        lambda request: httpx.Response(200, json={"error": {"message": "nope"}})
    )

    with pytest.raises(LLMProviderError) as error:
        await provider.generate([message()])

    assert error.value.code == "LLM_GENERATION_ERROR"


async def test_openai_stream_yields_deltas():
    lines = [
        'data: {"choices":[{"delta":{"content":"Ciao"}}]}',
        'data: {"choices":[{"delta":{"content":" mondo"}}]}',
        "data: [DONE]",
    ]
    provider = make_provider(
        lambda request: httpx.Response(200, content="\n".join(lines).encode())
    )

    chunks = [chunk async for chunk in provider.stream([message()])]

    assert chunks == ["Ciao", " mondo"]


async def test_openai_stream_http_error():
    provider = make_provider(lambda request: httpx.Response(500, text="boom"))

    with pytest.raises(LLMProviderError) as error:
        [chunk async for chunk in provider.stream([message()])]

    assert error.value.code == "LLM_HTTP_ERROR"


def test_openai_provider_rejects_empty_model():
    with pytest.raises(ValueError):
        OpenAIProvider("https://api.test/v1", "sk", "   ")


# --------------------------------------------------------------------------- #
# Capability                                                                   #
# --------------------------------------------------------------------------- #


def test_external_provider_disabled_by_flag(monkeypatch):
    monkeypatch.setenv("EXTERNAL_API_ENABLED", "false")
    get_settings.cache_clear()

    assert is_provider_available("external_api") is False


def test_external_provider_enabled_by_flag(monkeypatch):
    monkeypatch.setenv("EXTERNAL_API_ENABLED", "true")
    get_settings.cache_clear()

    assert is_provider_available("external_api") is True


# --------------------------------------------------------------------------- #
# External config + factory                                                    #
# --------------------------------------------------------------------------- #


async def test_external_config_is_encrypted_at_rest(session_factory):
    workspace_id = await create_workspace_row(session_factory)

    async with session_factory() as session:
        await set_external_config(
            session,
            workspace_id,
            base_url="https://api.test/v1",
            model="gpt-x",
            api_key="sk-secret",
        )
        await session.commit()

    async with session_factory() as session:
        config = await external_config(session, workspace_id)
        stored = await get_value(
            session,
            SettingScope.WORKSPACE,
            workspace_id,
            LLM_SETTING_TYPE,
            "external_api_key",
        )

    assert config is not None
    assert config.base_url == "https://api.test/v1"
    assert config.model == "gpt-x"
    assert config.api_key == "sk-secret"
    assert stored != "sk-secret"


async def test_external_config_none_when_incomplete(session_factory):
    workspace_id = await create_workspace_row(session_factory)

    async with session_factory() as session:
        assert await external_config(session, workspace_id) is None


async def test_build_provider_ollama(session_factory):
    workspace_id = await create_workspace_row(session_factory)

    async with session_factory() as session:
        provider, model = await build_provider(session, workspace_id, "ollama")

    assert provider.name == "ollama"
    assert model


async def test_build_provider_external_requires_config(session_factory):
    workspace_id = await create_workspace_row(session_factory)

    async with session_factory() as session:
        with pytest.raises(LLMProviderError) as error:
            await build_provider(session, workspace_id, "external_api")

    assert error.value.code == "PROVIDER_NOT_CONFIGURED"


async def test_build_provider_external_with_config(session_factory):
    workspace_id = await create_workspace_row(session_factory)

    async with session_factory() as session:
        await set_external_config(
            session, workspace_id, base_url="https://api.test/v1", model="gpt-x", api_key="sk"
        )
        await session.commit()

    async with session_factory() as session:
        provider, model = await build_provider(session, workspace_id, "external_api")

    assert isinstance(provider, OpenAIProvider)
    assert model == "gpt-x"


# --------------------------------------------------------------------------- #
# Endpoints                                                                    #
# --------------------------------------------------------------------------- #


async def create_workspace(client, headers, name="Acme") -> int:
    response = await client.post(
        "/api/v1/workspaces", json={"name": name}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_llm_config_lists_providers(client):
    headers = await register_and_login(client, "llm-config@example.com")
    workspace_id = await create_workspace(client, headers)

    response = await client.get(
        f"/api/v1/workspaces/{workspace_id}/llm/config", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert {provider["id"] for provider in body["providers"]} == {
        "ollama",
        "external_api",
    }
    assert body["default_provider"] == "ollama"


async def test_llm_settings_requires_admin(client, session_factory):
    owner = await register_and_login(client, "llm-owner@example.com")
    workspace_id = await create_workspace(client, owner)
    member = await register_and_login(client, "llm-member@example.com")
    member_id = await user_id_for(client, member)
    async with session_factory() as session:
        session.add(
            Membership(
                user_id=member_id, workspace_id=workspace_id, role=MembershipRole.MEMBER
            )
        )
        await session.commit()

    response = await client.get(
        f"/api/v1/workspaces/{workspace_id}/llm/settings", headers=member
    )

    assert response.status_code == 403


async def test_llm_settings_update_and_read(client, monkeypatch):
    monkeypatch.setenv("EXTERNAL_API_ENABLED", "true")
    get_settings.cache_clear()
    headers = await register_and_login(client, "llm-admin@example.com")
    workspace_id = await create_workspace(client, headers)

    response = await client.put(
        f"/api/v1/workspaces/{workspace_id}/llm/settings",
        json={
            "allowed_providers": ["ollama", "external_api"],
            "external_base_url": "https://api.test/v1",
            "external_model": "gpt-x",
            "external_api_key": "sk-secret",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["external_configured"] is True
    assert body["external_base_url"] == "https://api.test/v1"
    assert body["external_model"] == "gpt-x"
    assert "external_api_key" not in body

    config = await client.get(
        f"/api/v1/workspaces/{workspace_id}/llm/config", headers=headers
    )
    external = next(
        provider
        for provider in config.json()["providers"]
        if provider["id"] == "external_api"
    )
    assert external["models"] == ["gpt-x"]
    assert config.json()["allowed_providers"] == ["ollama", "external_api"]


async def test_llm_settings_partial_external_is_rejected(client, monkeypatch):
    monkeypatch.setenv("EXTERNAL_API_ENABLED", "true")
    get_settings.cache_clear()
    headers = await register_and_login(client, "llm-partial@example.com")
    workspace_id = await create_workspace(client, headers)

    response = await client.put(
        f"/api/v1/workspaces/{workspace_id}/llm/settings",
        json={"external_base_url": "https://api.test/v1"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INCOMPLETE_EXTERNAL_CONFIG"


async def test_llm_settings_update_keeps_existing_key(client, monkeypatch):
    monkeypatch.setenv("EXTERNAL_API_ENABLED", "true")
    get_settings.cache_clear()
    headers = await register_and_login(client, "llm-keepkey@example.com")
    workspace_id = await create_workspace(client, headers)
    await client.put(
        f"/api/v1/workspaces/{workspace_id}/llm/settings",
        json={
            "external_base_url": "https://api.test/v1",
            "external_model": "gpt-x",
            "external_api_key": "sk-secret",
        },
        headers=headers,
    )

    response = await client.put(
        f"/api/v1/workspaces/{workspace_id}/llm/settings",
        json={
            "external_base_url": "https://api.test/v2",
            "external_model": "gpt-y",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["external_configured"] is True
    assert body["external_base_url"] == "https://api.test/v2"
    assert body["external_model"] == "gpt-y"


async def test_select_provider_endpoint(client, session_factory, monkeypatch):
    monkeypatch.setenv("EXTERNAL_API_ENABLED", "true")
    get_settings.cache_clear()
    headers = await register_and_login(client, "llm-select@example.com")
    workspace_id = await create_workspace(client, headers)
    await client.put(
        f"/api/v1/workspaces/{workspace_id}/llm/settings",
        json={
            "allowed_providers": ["ollama", "external_api"],
            "external_base_url": "https://api.test/v1",
            "external_model": "gpt-x",
            "external_api_key": "sk-secret",
        },
        headers=headers,
    )

    response = await client.put(
        f"/api/v1/workspaces/{workspace_id}/llm/provider",
        json={"provider_id": "external_api"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["selected_provider"] == "external_api"


async def test_select_unavailable_provider_is_rejected(client):
    headers = await register_and_login(client, "llm-unavail@example.com")
    workspace_id = await create_workspace(client, headers)

    response = await client.put(
        f"/api/v1/workspaces/{workspace_id}/llm/provider",
        json={"provider_id": "external_api"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "PROVIDER_NOT_AVAILABLE"
