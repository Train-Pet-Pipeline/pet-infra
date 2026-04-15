"""Device and inference backend detection.

Usage:
    from pet_infra.device import detect_device
    device = detect_device()  # "cuda" / "mps" / "cpu" / "rknn" / "api"

Detection order:
    1. INFERENCE_BACKEND env var (if set, overrides auto-detection)
    2. CUDA (via torch.cuda.is_available)
    3. MPS (via torch.backends.mps.is_available)
    4. RKNN (via rknn_toolkit2 importability)
    5. CPU (fallback)
"""

from __future__ import annotations

import importlib
import os

_VALID_BACKENDS = {"cuda", "mps", "cpu", "rknn", "api"}


def detect_device() -> str:
    """Detect the best available compute device.

    Returns:
        One of: "cuda", "mps", "cpu", "rknn", "api".
    """
    env_backend = os.environ.get("INFERENCE_BACKEND", "").lower()
    if env_backend in _VALID_BACKENDS:
        return env_backend

    try:
        import torch
    except (ImportError, ModuleNotFoundError):
        torch = None  # type: ignore[assignment]

    if torch is not None:
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"

    try:
        importlib.import_module("rknn_toolkit2")
        return "rknn"
    except (ImportError, ModuleNotFoundError):
        pass

    return "cpu"
