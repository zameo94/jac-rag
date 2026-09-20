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

OLLAMA_PROVIDER_NAME = "ollama"
DEFAULT_TIMEOUT_SECONDS = 120.0
CHAT_PATH = "/api/chat"


class OllamaProvider(LLMProvider):
    """Local Ollama backend over its HTTP API.

    Only the selected provider runs for a request; this class performs no
    cross-provider fallback or orchestration.
    """

    name = OLLAMA_PROVIDER_NAME

    def __init__(
        self,
        base_url: str,
        default_model: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not default_model.strip():
            raise ValueError("default_model must not be empty")
        self._default_model = default_model
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
        )

    @property
    def default_model(self) -> str:
        return self._default_model

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

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
            "stream": stream,
            "options": {"temperature": temperature},
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
            response = await self._client.post(CHAT_PATH, json=payload)
        except httpx.TransportError as exc:
            raise LLMProviderError(
                "LLM_UNAVAILABLE", f"Ollama is unreachable: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise LLMProviderError(
                "LLM_HTTP_ERROR",
                f"Ollama returned status {response.status_code}: {response.text[:200]}",
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError(
                "LLM_INVALID_RESPONSE", "Ollama returned invalid JSON"
            ) from exc

        if data.get("error"):
            raise LLMProviderError("LLM_GENERATION_ERROR", str(data["error"]))

        message = data.get("message") or {}
        if "content" not in message:
            raise LLMProviderError(
                "LLM_INVALID_RESPONSE", "Ollama response has no message content"
            )

        return LLMResponse(
            content=message.get("content", ""),
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
            async with self._client.stream("POST", CHAT_PATH, json=payload) as response:
                if response.status_code >= 400:
                    await response.aread()
                    raise LLMProviderError(
                        "LLM_HTTP_ERROR",
                        f"Ollama returned status {response.status_code}",
                    )
                async for line in response.aiter_lines():
                    chunk = line.strip()
                    if not chunk:
                        continue
                    try:
                        data = json.loads(chunk)
                    except ValueError as exc:
                        raise LLMProviderError(
                            "LLM_INVALID_RESPONSE", "Ollama streamed invalid JSON"
                        ) from exc
                    if data.get("error"):
                        raise LLMProviderError(
                            "LLM_GENERATION_ERROR", str(data["error"])
                        )
                    piece = (data.get("message") or {}).get("content", "")
                    if piece:
                        yield piece
                    if data.get("done"):
                        break
        except httpx.TransportError as exc:
            raise LLMProviderError(
                "LLM_UNAVAILABLE", f"Ollama is unreachable: {exc}"
            ) from exc
