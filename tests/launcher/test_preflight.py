"""P1-D: cartesian sweep size preflight per spec §1.3 / §3.3 / R6.

Thresholds: warn >16, fail >64. PET_ALLOW_LARGE_SWEEP=1 overrides the fail.
"""
from __future__ import annotations

import logging

import pytest

from pet_infra.sweep_preflight import CartesianTooLargeError, check_cartesian_size


def test_under_16_silent(caplog: pytest.LogCaptureFixture) -> None:
    """Sizes <= warn threshold log nothing at WARNING level."""
    caplog.set_level(logging.WARNING, logger="pet_infra.sweep_preflight")
    check_cartesian_size(8)
    assert not any(r.levelname == "WARNING" for r in caplog.records)


def test_over_16_warns(caplog: pytest.LogCaptureFixture) -> None:
    """Sizes > warn threshold but <= fail threshold log a WARNING."""
    caplog.set_level(logging.WARNING, logger="pet_infra.sweep_preflight")
    check_cartesian_size(20)
    assert any(
        "warn" in r.message.lower() or "exceeds" in r.message.lower()
        for r in caplog.records
    )


def test_over_64_fails() -> None:
    """Sizes > fail threshold raise CartesianTooLargeError without override."""
    with pytest.raises(CartesianTooLargeError):
        check_cartesian_size(100)


def test_over_64_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """PET_ALLOW_LARGE_SWEEP=1 suppresses the fail."""
    monkeypatch.setenv("PET_ALLOW_LARGE_SWEEP", "1")
    check_cartesian_size(100)  # no raise
