"""Tests for pet_infra.api_client module."""

import asyncio

import httpx
import pytest
import respx

from pet_infra.api_client import ChatResponse, TeacherClient  # noqa: F401


def _ok_response(content: str = "Hello!") -> httpx.Response:
    """Helper to create a successful chat response."""
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


class TestTeacherClientInit:
    def test_default_init(self):
        client = TeacherClient(base_url="http://localhost:8000", api_key="test")
        assert client.base_url == "http://localhost:8000"

    def test_custom_concurrency(self):
        client = TeacherClient(
            base_url="http://localhost:8000", api_key="test", max_concurrency=5
        )
        assert client._semaphore._value == 5


class TestTeacherClientChat:
    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_chat(self):
        route = respx.post("http://localhost:8000/v1/chat/completions").mock(
            return_value=_ok_response("Hello!")
        )
        client = TeacherClient(base_url="http://localhost:8000", api_key="test-key")
        result = await client.chat("Say hello")
        assert result.content == "Hello!"
        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_retry_on_server_error(self):
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(500, json={"error": "internal"})
            return _ok_response("ok")

        respx.post("http://localhost:8000/v1/chat/completions").mock(side_effect=side_effect)
        client = TeacherClient(base_url="http://localhost:8000", api_key="test-key")
        result = await client.chat("test")
        assert result.content == "ok"
        assert call_count == 3

    @respx.mock
    @pytest.mark.asyncio
    async def test_429_retry(self):
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    429, headers={"Retry-After": "0"}, json={"error": "rate limited"}
                )
            return _ok_response("ok")

        respx.post("http://localhost:8000/v1/chat/completions").mock(side_effect=side_effect)
        client = TeacherClient(base_url="http://localhost:8000", api_key="test-key")
        result = await client.chat("test")
        assert result.content == "ok"
        assert call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        active = 0
        max_active = 0

        async def side_effect(request):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.05)
            active -= 1
            return _ok_response("ok")

        respx.post("http://localhost:8000/v1/chat/completions").mock(side_effect=side_effect)
        client = TeacherClient(
            base_url="http://localhost:8000", api_key="test-key", max_concurrency=2
        )
        tasks = [client.chat(f"msg-{i}") for i in range(5)]
        await asyncio.gather(*tasks)
        assert max_active <= 2
