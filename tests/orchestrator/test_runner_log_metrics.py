"""F027 regression test: pet_run() must call experiment_logger.log_metrics(card.metrics).

Without this, ClearML dashboard shows zero scalars even though card.metrics
carries train_loss / rewards/margins etc. (post F022/F023). log_model_card
attaches the card as a configuration JSON blob (searchable but not chartable);
scalar reporting requires log_metrics.
"""
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from pet_schema.model_card import ModelCard

from pet_infra.orchestrator.runner import pet_run
from pet_infra.registry import TRAINERS


class _ProbeTrainer:
    """Returns a card with non-empty metrics so we can assert log_metrics was called."""

    def __init__(self, **cfg):
        self.cfg = cfg

    def run(self, input_card, recipe):
        return ModelCard(
            id="PLACEHOLDER",
            version="0.1.0",
            modality="vision",
            task="sft",
            arch="probe",
            training_recipe="r",
            hydra_config_sha="s" * 40,
            git_shas={},
            dataset_versions={},
            checkpoint_uri="file:///tmp/probe",
            metrics={"train_loss": 0.42, "epoch": 0.5},
            gate_status="pending",
            trained_at=datetime.now(UTC),
            trained_by="test",
        )


def test_runner_calls_log_metrics_with_card_metrics(tmp_path: Path) -> None:
    """F027: pet_run must call experiment_logger.log_metrics({...}) with card.metrics."""
    TRAINERS.register_module(name="probe_log_metrics_trainer", module=_ProbeTrainer, force=True)

    recipe = {
        "recipe": {
            "recipe_id": "probe",
            "description": "F027 probe",
            "scope": "single_repo",
            "owner_repo": "pet-infra",
            "schema_version": "2.0.0",
            "stages": [
                {
                    "name": "train",
                    "component_registry": "trainers",
                    "component_type": "probe_log_metrics_trainer",
                    "inputs": {},
                    "config_path": str(tmp_path / "empty.yaml"),
                    "depends_on": [],
                }
            ],
            "variations": [],
            "produces": [],
            "default_storage": "local",
            "required_plugins": ["pet_infra"],
        }
    }
    (tmp_path / "empty.yaml").write_text("{}\n")
    recipe_path = tmp_path / "recipe.yaml"
    recipe_path.write_text(yaml.dump(recipe))

    fake_logger = MagicMock()
    fake_logger.start.return_value = "task-123"

    with patch("pet_infra.orchestrator.runner.build_experiment_logger", return_value=fake_logger):
        pet_run(recipe_path, resume=False, cache_root=tmp_path / "cache")

    # F027 assertion: log_metrics MUST be called with card.metrics
    fake_logger.log_metrics.assert_called_once()
    call_args = fake_logger.log_metrics.call_args
    metrics_arg = call_args[0][0] if call_args[0] else call_args[1]["metrics"]
    assert metrics_arg["train_loss"] == 0.42
    assert metrics_arg["epoch"] == 0.5


def test_runner_skips_log_metrics_when_card_metrics_empty(tmp_path: Path) -> None:
    """F027: empty card.metrics → log_metrics NOT called (avoid ClearML noise)."""

    class _EmptyMetricsTrainer:
        def __init__(self, **cfg):
            pass

        def run(self, input_card, recipe):
            return ModelCard(
                id="PLACEHOLDER",
                version="0.1.0",
                modality="vision",
                task="sft",
                arch="empty",
                training_recipe="r",
                hydra_config_sha="s" * 40,
                git_shas={},
                dataset_versions={},
                checkpoint_uri="file:///tmp/empty",
                metrics={},  # F027: explicitly empty
                gate_status="pending",
                trained_at=datetime.now(UTC),
                trained_by="test",
            )

    TRAINERS.register_module(name="empty_metrics_trainer", module=_EmptyMetricsTrainer, force=True)

    recipe = {
        "recipe": {
            "recipe_id": "empty",
            "description": "F027 empty probe",
            "scope": "single_repo",
            "owner_repo": "pet-infra",
            "schema_version": "2.0.0",
            "stages": [
                {
                    "name": "train",
                    "component_registry": "trainers",
                    "component_type": "empty_metrics_trainer",
                    "inputs": {},
                    "config_path": str(tmp_path / "empty.yaml"),
                    "depends_on": [],
                }
            ],
            "variations": [],
            "produces": [],
            "default_storage": "local",
            "required_plugins": ["pet_infra"],
        }
    }
    (tmp_path / "empty.yaml").write_text("{}\n")
    recipe_path = tmp_path / "recipe.yaml"
    recipe_path.write_text(yaml.dump(recipe))

    fake_logger = MagicMock()
    fake_logger.start.return_value = "task-456"

    with patch("pet_infra.orchestrator.runner.build_experiment_logger", return_value=fake_logger):
        pet_run(recipe_path, resume=False, cache_root=tmp_path / "cache")

    fake_logger.log_metrics.assert_not_called()
