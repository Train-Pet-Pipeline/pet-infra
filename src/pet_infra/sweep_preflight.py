"""Cartesian sweep size preflight per spec §1.3 / §3.3 / R6.

Bookends the variations launcher and the CLI multirun path: any sweep that
expands to more than ``WARN_THRESHOLD`` runs logs a WARNING; more than
``FAIL_THRESHOLD`` raises ``CartesianTooLargeError`` unless the operator
explicitly sets ``PET_ALLOW_LARGE_SWEEP=1`` to acknowledge GPU/budget cost.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

WARN_THRESHOLD = 16
FAIL_THRESHOLD = 64
OVERRIDE_ENV = "PET_ALLOW_LARGE_SWEEP"


class CartesianTooLargeError(RuntimeError):
    """Raised when a sweep's cartesian size exceeds the fail threshold."""


def check_cartesian_size(n: int) -> None:
    """Validate a sweep cartesian size against the configured thresholds.

    Args:
        n: Total number of runs the sweep would dispatch.

    Raises:
        CartesianTooLargeError: When ``n > FAIL_THRESHOLD`` and the operator
            has not set ``PET_ALLOW_LARGE_SWEEP=1`` to override.
    """
    if n > FAIL_THRESHOLD and os.environ.get(OVERRIDE_ENV) != "1":
        raise CartesianTooLargeError(
            f"Sweep size {n} exceeds fail threshold {FAIL_THRESHOLD}; "
            f"set {OVERRIDE_ENV}=1 to override."
        )
    if n > WARN_THRESHOLD:
        logger.warning(
            "Sweep size %d exceeds warn threshold %d; consider trimming axes.",
            n,
            WARN_THRESHOLD,
        )
