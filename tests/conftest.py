"""Shared test fixtures for pet-infra."""

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def set_allow_missing_sdk() -> None:
    """Set PET_ALLOW_MISSING_SDK=1 for the entire test session.

    The pet-pipeline shared conda env has pet-quantize and pet-ota installed.
    Their _register.py unconditionally imports RKNN-gated SDKs unless this
    env var is set, causing 10+ failures on any shared-env machine.

    CI uses a clean env where this is a no-op. Local dev requires this guard.
    Mirrors the pattern already used by pet-eval's pytest config.
    """
    os.environ.setdefault("PET_ALLOW_MISSING_SDK", "1")
