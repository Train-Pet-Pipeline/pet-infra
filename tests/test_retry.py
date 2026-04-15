"""Tests for pet_infra.retry module."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from tenacity import RetryError

from pet_infra.retry import standard_retry, standard_retry_async


class TestStandardRetry:
    def test_succeeds_on_first_try(self):
        mock_fn = MagicMock(return_value="ok")
        decorated = standard_retry(mock_fn)
        assert decorated() == "ok"
        assert mock_fn.call_count == 1

    def test_retries_on_failure(self):
        mock_fn = MagicMock(side_effect=[ValueError, ValueError, "ok"])
        decorated = standard_retry(mock_fn, wait_min=0, wait_max=0)
        assert decorated() == "ok"
        assert mock_fn.call_count == 3

    def test_raises_after_max_attempts(self):
        mock_fn = MagicMock(side_effect=ValueError("fail"))
        decorated = standard_retry(mock_fn, wait_min=0, wait_max=0)
        with pytest.raises(RetryError):
            decorated()
        assert mock_fn.call_count == 3

    def test_custom_max_attempts(self):
        mock_fn = MagicMock(side_effect=ValueError("fail"))
        decorated = standard_retry(mock_fn, max_attempts=5, wait_min=0, wait_max=0)
        with pytest.raises(RetryError):
            decorated()
        assert mock_fn.call_count == 5


class TestStandardRetryAsync:
    @pytest.mark.asyncio
    async def test_async_succeeds_on_first_try(self):
        mock_fn = AsyncMock(return_value="ok")
        decorated = standard_retry_async(mock_fn)
        assert await decorated() == "ok"
        assert mock_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_async_retries_on_failure(self):
        mock_fn = AsyncMock(side_effect=[ValueError, "ok"])
        decorated = standard_retry_async(mock_fn, wait_min=0, wait_max=0)
        assert await decorated() == "ok"
        assert mock_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_async_raises_after_max_attempts(self):
        mock_fn = AsyncMock(side_effect=ValueError("fail"))
        decorated = standard_retry_async(mock_fn, wait_min=0, wait_max=0)
        with pytest.raises(RetryError):
            await decorated()
        assert mock_fn.call_count == 3
