"""Standard retry configuration for external API calls.

Usage:
    from pet_infra.retry import standard_retry, standard_retry_async

    @standard_retry
    def call_api():
        ...

    @standard_retry_async
    async def call_api_async():
        ...

Defaults from params.yaml: exponential backoff 2-30s, max 3 attempts.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import yaml
from tenacity import retry, stop_after_attempt, wait_exponential

F = TypeVar("F", bound=Callable[..., Any])

# Load defaults from params.yaml
_params_path = Path(__file__).resolve().parents[2] / "params.yaml"
if _params_path.exists():
    with open(_params_path) as f:
        _cfg = yaml.safe_load(f).get("retry", {})
else:
    _cfg = {}

_DEFAULT_MAX_ATTEMPTS = _cfg.get("max_attempts", 3)
_DEFAULT_WAIT_MIN = _cfg.get("wait_min", 2)
_DEFAULT_WAIT_MAX = _cfg.get("wait_max", 30)
_DEFAULT_MULTIPLIER = _cfg.get("multiplier", 1)


def standard_retry(
    fn: F | None = None,
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    wait_min: int = _DEFAULT_WAIT_MIN,
    wait_max: int = _DEFAULT_WAIT_MAX,
    multiplier: int = _DEFAULT_MULTIPLIER,
) -> Any:
    """Apply standard retry policy to a synchronous function.

    Can be used as bare decorator (@standard_retry) or with params
    (@standard_retry(max_attempts=5)).

    Args:
        fn: Function to decorate. If None, returns a partial decorator.
        max_attempts: Max retry attempts (default from params.yaml: 3).
        wait_min: Minimum wait seconds (default: 2).
        wait_max: Maximum wait seconds (default: 30).
        multiplier: Exponential backoff multiplier (default: 1).
    """
    decorator = retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=multiplier, min=wait_min, max=wait_max),
        reraise=False,
    )
    if fn is not None:
        return decorator(fn)
    return decorator


def standard_retry_async(
    fn: F | None = None,
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    wait_min: int = _DEFAULT_WAIT_MIN,
    wait_max: int = _DEFAULT_WAIT_MAX,
    multiplier: int = _DEFAULT_MULTIPLIER,
) -> Any:
    """Apply standard retry policy to an asynchronous function.

    Args:
        fn: Async function to decorate. If None, returns a partial decorator.
        max_attempts: Max retry attempts (default from params.yaml: 3).
        wait_min: Minimum wait seconds (default: 2).
        wait_max: Maximum wait seconds (default: 30).
        multiplier: Exponential backoff multiplier (default: 1).
    """
    decorator = retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=multiplier, min=wait_min, max=wait_max),
        reraise=False,
    )
    if fn is not None:
        return decorator(fn)
    return decorator
