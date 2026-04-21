"""`pet validate --card=<path> --hardware=rk3576 [--dry-run]` command.

Phase 3B scope: --dry-run implemented (writes stub HardwareValidation).
Real-device execution deferred to manual release-manager workflow
(CLAUDE.md: latency tests run on real RK3576 only).
"""
from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path

import click
from pet_schema.model_card import HardwareValidation, ModelCard

_VALIDATED_BY_RE = re.compile(r"^(github-actions|operator):[A-Za-z0-9_.\-]+$")


def _derive_validated_by(explicit: str | None) -> str:
    r"""Derive the validated_by string from env or explicit override.

    Args:
        explicit: Optional explicit override from --validated-by CLI flag.

    Returns:
        A string matching ``^(github-actions|operator):[A-Za-z0-9_.\-]+$``.

    Raises:
        click.ClickException: When the derived value doesn't match the schema regex.
    """
    if explicit:
        who = explicit
    elif os.environ.get("GITHUB_RUN_ID"):
        who = f"github-actions:{os.environ['GITHUB_RUN_ID']}"
    else:
        user = os.environ.get("USER", "unknown")
        # Sanitize: keep only regex-safe chars to avoid schema validation failure
        user = re.sub(r"[^A-Za-z0-9_.\-]", "_", user)
        who = f"operator:{user}"

    if not _VALIDATED_BY_RE.fullmatch(who):
        raise click.ClickException(
            f"Derived validated_by={who!r} does not match schema regex "
            r"^(github-actions|operator):[A-Za-z0-9_.\-]+$. "
            "Pass --validated-by <value> explicitly."
        )
    return who


def run_hardware_validate(
    card_path: Path,
    hardware: str,
    device_id: str,
    firmware_version: str,
    dry_run: bool,
    validated_by: str | None,
) -> None:
    """Write a HardwareValidation stub to a ModelCard JSON file.

    Args:
        card_path: Path to the ModelCard JSON file to update.
        hardware: Target hardware platform (e.g. ``rk3576``).
        device_id: Device identifier string.
        firmware_version: Firmware version string.
        dry_run: When True write a stub; when False raise ClickException.
        validated_by: Optional explicit validated_by override.

    Raises:
        click.ClickException: When not in dry_run mode (real-device not implemented).
    """
    card = ModelCard.model_validate_json(card_path.read_text())
    if not dry_run:
        raise click.ClickException(
            "Real-device validation not implemented in Phase 3B. "
            "Use --dry-run for CI or write HardwareValidation programmatically."
        )
    who = _derive_validated_by(validated_by)
    hv = HardwareValidation(
        device_id=device_id,
        firmware_version=firmware_version,
        validated_at=datetime.now(UTC),
        latency_ms_p50=0.0,
        latency_ms_p95=0.0,
        accuracy=None,
        kl_divergence=None,
        validated_by=who,
        notes="DRY-RUN stub; not a real validation",
    )
    updated = card.model_copy(update={"hardware_validation": hv})
    card_path.write_text(updated.model_dump_json(indent=2))
    click.echo(f"OK HardwareValidation written to {card_path} (validated_by={who})")
