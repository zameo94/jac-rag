from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

import httpx

from app.services.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
)

EXTERNAL_API_PROVIDER_NAME = "external_api"
DEFAULT_TIMEOUT_SECONDS = 120.0
CHAT_PATH = "/chat/completions"


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible chat provider (OpenAI, OpenRouter, OpenCode, vLLM...).

    The tenant configures ``base_url``, ``api_key`` and ``model``; a request uses
    exactly this provider, with no cross-provider fallback.
    """

    name = EXTERNAL_API_PROVIDER_NAME

    def __init__(
        self,
        base_url: str,
        api_key: str,
        default_model: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not default_model.strip():
            raise ValueError("default_model must not be empty")
        self._default_model = default_model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    @property
    def default_model(self) -> str:
        return self._default_model

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _payload(
        self,
        messages: Sequence[LLMMessage],
        model: str | None,
        temperature: float,
        *,
        stream: bool,
    ) -> dict:
        return {
            "model": model or self._default_model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in messages
            ],
            "temperature": temperature,
            "stream": stream,
        }

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        payload = self._payload(messages, model, temperature, stream=False)
        try:
            response = await self._client.post(
                f"{self._base_url}{CHAT_PATH}",
                json=payload,
                headers=self._headers(),
            )
        except httpx.TransportError as exc:
            raise LLMProviderError(
                "LLM_UNAVAILABLE", f"External provider is unreachable: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise LLMProviderError(
                "LLM_HTTP_ERROR",
                f"External provider returned status {response.status_code}: "
                f"{response.text[:200]}",
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError(
                "LLM_INVALID_RESPONSE", "External provider returned invalid JSON"
            ) from exc

        if data.get("error"):
            error = data["error"]
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise LLMProviderError("LLM_GENERATION_ERROR", message)

        choices = data.get("choices") or []
        if not choices:
            raise LLMProviderError(
                "LLM_INVALID_RESPONSE", "External provider returned no choices"
            )
        content = (choices[0].get("message") or {}).get("content")

        return LLMResponse(
            content=content or "",
            model=str(data.get("model") or payload["model"]),
            provider=self.name,
        )

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        payload = self._payload(messages, model, temperature, stream=True)
        try:
            async with self._client.stream(
                "POST",
                f"{self._base_url}{CHAT_PATH}",
                json=payload,
                headers=self._headers(),
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    raise LLMProviderError(
                        "LLM_HTTP_ERROR",
                        f"External provider returned status {response.status_code}",
                    )
                async for line in response.aiter_lines():
                    chunk = line.strip()
                    if not chunk or not chunk.startswith("data:"):
                        continue
                    data = chunk[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except ValueError as exc:
                        raise LLMProviderError(
                            "LLM_INVALID_RESPONSE",
                            "External provider streamed invalid JSON",
                        ) from exc
                    if event.get("error"):
                        raise LLMProviderError(
                            "LLM_GENERATION_ERROR", str(event["error"])
                        )
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    piece = (choices[0].get("delta") or {}).get("content")
                    if piece:
                        yield piece
        except httpx.TransportError as exc:
            raise LLMProviderError(
                "LLM_UNAVAILABLE", f"External provider is unreachable: {exc}"
            ) from exc
