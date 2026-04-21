"""Tests for `pet validate --hardware` CLI skeleton (Phase 3B P1-E)."""
from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from pet_schema.model_card import HardwareValidation, ModelCard

# Resolve `pet` from the same Python environment running this test suite,
# avoiding accidental use of a `pet` binary from a different conda environment.
_PET_BIN = str(Path(sys.executable).parent / "pet")


def _make_card_kwargs(gate_status: str = "passed") -> dict:
    return dict(
        id="rel-123",
        version="v1",
        modality="vision",
        task="classification",
        arch="resnet",
        training_recipe="smoke_tiny",
        hydra_config_sha="abc123",
        git_shas={"pet-train": "deadbeef"},
        dataset_versions={"imagenet": "v1"},
        checkpoint_uri="file:///tmp/x.pt",
        metrics={"accuracy": 0.9},
        gate_status=gate_status,
        trained_at=datetime(2026, 4, 21, tzinfo=UTC),
        trained_by="tester",
    )


def _write_card(tmp_path: Path, with_validation: bool = False) -> Path:
    card = ModelCard(**_make_card_kwargs())
    if with_validation:
        hv = HardwareValidation(
            device_id="rk3576-x",
            firmware_version="1.0",
            validated_at=datetime.now(UTC),
            latency_ms_p50=10.0,
            latency_ms_p95=20.0,
            validated_by="operator:test",
        )
        card = card.model_copy(update={"hardware_validation": hv})
    p = tmp_path / "card.json"
    p.write_text(card.model_dump_json())
    return p


def test_cli_skeleton_exposes_hardware_flag() -> None:
    """pet validate --help must list --hardware option."""
    r = subprocess.run([_PET_BIN, "validate", "--help"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "--hardware" in r.stdout


def test_cli_dry_run_writes_hardware_validation(tmp_path: Path) -> None:
    """--dry-run must write a HardwareValidation stub into the card file."""
    card_path = _write_card(tmp_path)
    r = subprocess.run(
        [
            _PET_BIN,
            "validate",
            "--card",
            str(card_path),
            "--hardware",
            "rk3576",
            "--device",
            "rk3576-test-01",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    updated = ModelCard.model_validate_json(card_path.read_text())
    assert updated.hardware_validation is not None
    who = updated.hardware_validation.validated_by
    assert who.startswith("github-actions:") or who.startswith("operator:")


def test_cli_without_dry_run_errors(tmp_path: Path) -> None:
    """Omitting --dry-run must exit non-zero with a clear message."""
    card_path = _write_card(tmp_path)
    r = subprocess.run(
        [
            _PET_BIN,
            "validate",
            "--card",
            str(card_path),
            "--hardware",
            "rk3576",
            "--device",
            "rk3576-test-01",
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0
    assert "Real-device" in r.stderr or "not implemented" in r.stderr


def test_cli_explicit_validated_by_override(tmp_path: Path) -> None:
    """--validated-by must be used verbatim in the written HardwareValidation."""
    card_path = _write_card(tmp_path)
    r = subprocess.run(
        [
            _PET_BIN,
            "validate",
            "--card",
            str(card_path),
            "--hardware",
            "rk3576",
            "--device",
            "rk3576-test-01",
            "--dry-run",
            "--validated-by",
            "operator:release-bot",
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    updated = ModelCard.model_validate_json(card_path.read_text())
    assert updated.hardware_validation is not None
    assert updated.hardware_validation.validated_by == "operator:release-bot"
