import json

import httpx
import pytest

from app.services.llm import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRole,
    OllamaProvider,
)

DEFAULT_MODEL = "llama3.2"


def user_message(text: str = "ciao") -> LLMMessage:
    return LLMMessage(role=LLMRole.USER, content=text)


def make_provider(handler, default_model: str = DEFAULT_MODEL) -> OllamaProvider:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://ollama.test",
    )
    return OllamaProvider("http://ollama.test", default_model, client=client)


async def collect(stream) -> list[str]:
    return [chunk async for chunk in stream]


def test_ollama_provider_implements_contract():
    provider = make_provider(lambda request: httpx.Response(200, json={}))

    assert isinstance(provider, LLMProvider)
    assert provider.name == "ollama"
    assert provider.default_model == DEFAULT_MODEL


def test_ollama_provider_rejects_empty_default_model():
    with pytest.raises(ValueError):
        OllamaProvider("http://ollama.test", "   ")


async def test_generate_returns_content_and_default_payload():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": DEFAULT_MODEL,
                "message": {"role": "assistant", "content": "Ciao"},
                "done": True,
            },
        )

    provider = make_provider(handler)

    result = await provider.generate([user_message()])

    assert result.content == "Ciao"
    assert result.model == DEFAULT_MODEL
    assert result.provider == "ollama"
    assert captured["path"] == "/api/chat"
    assert captured["payload"] == {
        "model": DEFAULT_MODEL,
        "messages": [{"role": "user", "content": "ciao"}],
        "stream": False,
        "options": {"temperature": 0.0},
    }


async def test_generate_respects_model_override_and_temperature():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "custom-model",
                "message": {"role": "assistant", "content": "ok"},
                "done": True,
            },
        )

    provider = make_provider(handler)

    result = await provider.generate(
        [user_message()], model="custom-model", temperature=0.7
    )

    assert captured["payload"]["model"] == "custom-model"
    assert captured["payload"]["options"] == {"temperature": 0.7}
    assert result.model == "custom-model"


async def test_generate_raises_on_http_error():
    provider = make_provider(
        lambda request: httpx.Response(404, json={"error": "model not found"})
    )

    with pytest.raises(LLMProviderError) as error:
        await provider.generate([user_message()])

    assert error.value.code == "LLM_HTTP_ERROR"
    assert "404" in error.value.message


async def test_generate_raises_when_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = make_provider(handler)

    with pytest.raises(LLMProviderError) as error:
        await provider.generate([user_message()])

    assert error.value.code == "LLM_UNAVAILABLE"


async def test_generate_raises_on_invalid_json():
    provider = make_provider(
        lambda request: httpx.Response(200, text="not-json")
    )

    with pytest.raises(LLMProviderError) as error:
        await provider.generate([user_message()])

    assert error.value.code == "LLM_INVALID_RESPONSE"


async def test_generate_raises_on_error_field():
    provider = make_provider(
        lambda request: httpx.Response(200, json={"error": "boom"})
    )

    with pytest.raises(LLMProviderError) as error:
        await provider.generate([user_message()])

    assert error.value.code == "LLM_GENERATION_ERROR"


async def test_generate_raises_when_content_missing():
    provider = make_provider(
        lambda request: httpx.Response(200, json={"model": DEFAULT_MODEL, "done": True})
    )

    with pytest.raises(LLMProviderError) as error:
        await provider.generate([user_message()])

    assert error.value.code == "LLM_INVALID_RESPONSE"


async def test_stream_yields_text_chunks_and_sends_stream_payload():
    captured: dict = {}
    lines = [
        json.dumps({"message": {"content": "Ciao"}, "done": False}),
        json.dumps({"message": {"content": " mondo"}, "done": False}),
        json.dumps({"message": {"content": ""}, "done": True}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, content="\n".join(lines).encode())

    provider = make_provider(handler)

    chunks = await collect(provider.stream([user_message()]))

    assert chunks == ["Ciao", " mondo"]
    assert captured["payload"]["stream"] is True


async def test_stream_stops_at_done():
    lines = [
        json.dumps({"message": {"content": "primo"}, "done": False}),
        json.dumps({"message": {"content": ""}, "done": True}),
        json.dumps({"message": {"content": "dopo-done"}, "done": False}),
    ]

    provider = make_provider(
        lambda request: httpx.Response(200, content="\n".join(lines).encode())
    )

    chunks = await collect(provider.stream([user_message()]))

    assert chunks == ["primo"]


async def test_stream_raises_on_error_line():
    body = json.dumps({"error": "model not found"})

    provider = make_provider(
        lambda request: httpx.Response(200, content=body.encode())
    )

    with pytest.raises(LLMProviderError) as error:
        await collect(provider.stream([user_message()]))

    assert error.value.code == "LLM_GENERATION_ERROR"


async def test_stream_raises_on_http_error():
    provider = make_provider(lambda request: httpx.Response(500, text="boom"))

    with pytest.raises(LLMProviderError) as error:
        await collect(provider.stream([user_message()]))

    assert error.value.code == "LLM_HTTP_ERROR"


async def test_stream_raises_when_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = make_provider(handler)

    with pytest.raises(LLMProviderError) as error:
        await collect(provider.stream([user_message()]))

    assert error.value.code == "LLM_UNAVAILABLE"


async def test_aclose_does_not_close_injected_client():
    provider = make_provider(lambda request: httpx.Response(200, json={}))

    await provider.aclose()

    assert provider._client.is_closed is False
    await provider._client.aclose()
