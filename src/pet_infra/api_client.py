"""Unified teacher model API client with retry and rate limiting.

Usage:
    from pet_infra.api_client import TeacherClient

    client = TeacherClient(base_url="http://localhost:8000", api_key="sk-...")
    result = await client.chat("Describe the pet behavior in this image.")
    print(result.content)

Supports OpenAI-compatible APIs (vLLM, cloud providers).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


@dataclass
class ChatResponse:
    """Response from a chat completion call."""

    content: str
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    logprobs: list[dict[str, Any]] | None = None


def _is_retryable(exc: BaseException) -> bool:
    """Determine if an exception warrants a retry."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, httpx.ConnectError | httpx.ReadTimeout | httpx.WriteTimeout)


class TeacherClient:
    """Async client for OpenAI-compatible teacher model APIs.

    Args:
        base_url: API base URL (e.g. "http://localhost:8000").
        api_key: API key for authentication.
        model: Model name to use in requests. Defaults to "default".
        max_concurrency: Maximum concurrent requests. Defaults to 10.
        timeout: Request timeout in seconds. Defaults to 60.
        max_retries: Maximum retry attempts. Defaults to 3.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "default",
        max_concurrency: int = 10,
        timeout: float = 60,
        max_retries: int = 3,
    ) -> None:
        """Initialize the client."""
        self.base_url = base_url.rstrip("/")
        self._model = model
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout),
        )

    async def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        logprobs: bool = False,
    ) -> ChatResponse:
        """Send a chat completion request.

        Args:
            prompt: User message content.
            system: Optional system message.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            logprobs: Whether to request log probabilities.

        Returns:
            ChatResponse with content, usage, and optional logprobs.
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if logprobs:
            payload["logprobs"] = True

        @retry(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=0, max=1),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        )
        async def _do_request() -> ChatResponse:
            async with self._semaphore:
                resp = await self._client.post("/v1/chat/completions", json=payload)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        await asyncio.sleep(float(retry_after))
                    raise httpx.HTTPStatusError(
                        "Rate limited", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                data = resp.json()
                choice = data["choices"][0]
                return ChatResponse(
                    content=choice["message"]["content"],
                    finish_reason=choice.get("finish_reason", "stop"),
                    usage=data.get("usage", {}),
                    logprobs=choice.get("logprobs"),
                )

        return await _do_request()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
