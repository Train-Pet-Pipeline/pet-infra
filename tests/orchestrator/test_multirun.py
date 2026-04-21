"""Tests for Hydra multirun launcher guard in the `pet run -m` CLI command."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pet_schema
import pytest
import yaml
from click.testing import CliRunner

from pet_infra.cli import main
from pet_infra.registry import EVALUATORS, TRAINERS


def _make_card(card_id: str, task: str):
    """Create a minimal valid ModelCard for testing."""
    from pet_schema.model_card import ModelCard

    return ModelCard(
        id=card_id,
        version="0.1.0",
        modality="vision",
        task=task,
        arch="fake",
        training_recipe="r",
        hydra_config_sha="s" * 40,
        git_shas={},
        dataset_versions={},
        checkpoint_uri=f"file:///tmp/{task}",
        metrics={"loss": 0.1},
        gate_status="pending",
        trained_at=datetime.utcnow(),
        trained_by="test",
    )


class MultirunFakeSFTTrainer:
    """Fake trainer plugin for multirun guard tests."""

    def __init__(self, **cfg):
        """Initialize with config kwargs."""
        self.cfg = cfg

    def run(self, input_card, recipe):
        """Return a fake ModelCard."""
        return _make_card(card_id="PLACEHOLDER", task="sft")


class MultirunFakeEvaluator:
    """Fake evaluator plugin for multirun guard tests."""

    def __init__(self, **cfg):
        """Initialize with config kwargs."""
        self.cfg = cfg

    def run(self, input_card, recipe):
        """Return a fake ModelCard."""
        return _make_card(card_id="PLACEHOLDER", task="eval")


@pytest.fixture(autouse=True)
def _register_fakes():
    """Register fake plugins before each test and unregister after."""
    TRAINERS.register_module(name="multirun_fake_sft", module=MultirunFakeSFTTrainer, force=True)
    EVALUATORS.register_module(name="multirun_fake_eval", module=MultirunFakeEvaluator, force=True)
    yield
    TRAINERS.module_dict.pop("multirun_fake_sft", None)
    EVALUATORS.module_dict.pop("multirun_fake_eval", None)


def _write_recipe(tmp_path: Path) -> Path:
    """Write a minimal valid recipe YAML to tmp_path using fake plugins."""
    train_cfg = tmp_path / "train_cfg.yaml"
    train_cfg.write_text("lr: 0.0001\n")

    recipe = {
        "recipe": {
            "recipe_id": "test_multirun_guard",
            "description": "multirun guard test recipe",
            "scope": "single_repo",
            "schema_version": pet_schema.SCHEMA_VERSION,
            "stages": [
                {
                    "name": "train",
                    "component_registry": "trainers",
                    "component_type": "multirun_fake_sft",
                    "inputs": {},
                    "config_path": str(train_cfg),
                    "depends_on": [],
                },
            ],
            "variations": [],
            "produces": [],
            "default_storage": "local",
            "required_plugins": [],
        },
        "experiment_logger": {"name": "null"},
    }
    p = tmp_path / "recipe.yaml"
    p.write_text(yaml.safe_dump(recipe))
    return p


class TestMultirunBasicLauncherAllowed:
    """pet run -m without a non-basic launcher override should not be rejected by the guard."""

    def test_basic_launcher_allowed(self, tmp_path: Path) -> None:
        """Default (no launcher override) multirun does not trigger the guard error."""
        recipe_path = _write_recipe(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["run", str(recipe_path), "-m", "train.lr=1e-4,3e-4"],
        )
        # Guard must NOT fire — no "parallel" rejection message
        assert "parallel Hydra launchers" not in (result.output + (result.stderr or ""))

    def test_explicit_basic_launcher_allowed(self, tmp_path: Path) -> None:
        """Explicitly specifying hydra/launcher=basic does not trigger the guard."""
        recipe_path = _write_recipe(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["run", str(recipe_path), "-m", "train.lr=1e-4,3e-4", "hydra/launcher=basic"],
        )
        # Guard must NOT fire
        assert "parallel Hydra launchers" not in (result.output + (result.stderr or ""))


class TestMultirunParallelLauncherRejected:
    """pet run -m with a non-basic launcher override must exit non-zero with a clear error."""

    def test_joblib_launcher_rejected(self, tmp_path: Path) -> None:
        """hydra/launcher=joblib triggers the guard: non-zero exit + actionable message."""
        recipe_path = _write_recipe(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["run", str(recipe_path), "-m", "train.lr=1e-4,3e-4", "hydra/launcher=joblib"],
        )
        assert result.exit_code != 0
        assert "parallel" in result.output.lower()

    def test_ray_launcher_rejected(self, tmp_path: Path) -> None:
        """hydra/launcher=ray triggers the guard: non-zero exit."""
        recipe_path = _write_recipe(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["run", str(recipe_path), "-m", "train.lr=1e-4,3e-4", "hydra/launcher=ray"],
        )
        assert result.exit_code != 0
        assert "parallel" in result.output.lower()

    def test_submitit_launcher_rejected(self, tmp_path: Path) -> None:
        """hydra/launcher=submitit triggers the guard: non-zero exit."""
        recipe_path = _write_recipe(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["run", str(recipe_path), "-m", "train.lr=1e-4,3e-4", "hydra/launcher=submitit"],
        )
        assert result.exit_code != 0
        assert "parallel" in result.output.lower()
