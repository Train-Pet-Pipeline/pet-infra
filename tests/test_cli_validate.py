"""Tests for `pet validate --recipe` CLI subcommand."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from pet_infra.cli import main
from pet_infra.registry import TRAINERS

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "recipe"
SMOKE_RECIPE = str(FIXTURES_DIR / "smoke_cli.yaml")


@pytest.fixture()
def fake_trainer_registered():
    """Register fake_trainer in TRAINERS, then teardown."""

    @TRAINERS.register_module(name="fake_trainer")
    class FakeTrainer:
        """Fake trainer for CLI tests."""

    yield
    TRAINERS._module_dict.pop("fake_trainer", None)


class TestValidateHappyPath:
    """validate exits 0 and prints 'preflight: OK' for a valid recipe."""

    def test_happy_path(self, fake_trainer_registered: None) -> None:
        """Registered fake_trainer + valid recipe → exit 0 + 'preflight: OK'."""
        runner = CliRunner()
        result = runner.invoke(main, ["validate", f"--recipe={SMOKE_RECIPE}"])
        exc_msg = str(result.exception) if result.exception else ""
        assert result.exit_code == 0, result.output + exc_msg
        assert "preflight: OK" in result.output


class TestValidateUnregisteredComponent:
    """validate exits non-zero and reports PreflightError for unknown component."""

    def test_unregistered_component(self) -> None:
        """Recipe referencing 'sft_lora' (unregistered) → exit != 0, output has PreflightError."""
        runner = CliRunner()
        # Use minimal.yaml which references sft_lora (unregistered in tests)
        minimal = str(FIXTURES_DIR / "minimal.yaml")
        result = runner.invoke(main, ["validate", f"--recipe={minimal}"])
        assert result.exit_code != 0
        assert "PreflightError" in result.output


class TestValidateDumpResolved:
    """validate --dump-resolved prints JSON config before preflight: OK."""

    def test_override_and_dump_resolved(self, fake_trainer_registered: None) -> None:
        """--override description=hello --dump-resolved prints JSON with updated description."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "validate",
                f"--recipe={SMOKE_RECIPE}",
                "--override", "description=hello",
                "--dump-resolved",
            ],
        )
        exc_msg = str(result.exception) if result.exception else ""
        assert result.exit_code == 0, result.output + exc_msg
        # Output should contain the JSON blob before preflight: OK
        output = result.output
        # Find the JSON blob (everything before 'preflight: OK')
        ok_idx = output.find("preflight: OK")
        assert ok_idx != -1, "Expected 'preflight: OK' in output"
        json_blob = output[:ok_idx].strip()
        data = json.loads(json_blob)
        assert data["description"] == "hello"
