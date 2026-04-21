# tests/orchestrator/test_runner_resume.py
"""Integration tests for pet_run resume behavior using in-memory fake plugins."""
from datetime import datetime
from pathlib import Path

import pet_schema
import pytest
import yaml
from pet_schema.model_card import ModelCard

from pet_infra.orchestrator.runner import pet_run
from pet_infra.registry import EVALUATORS, TRAINERS

CALL_LOG: list[str] = []


def _make_card(card_id: str, task: str) -> ModelCard:
    """Create a minimal valid ModelCard for testing."""
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


class FakeSFTTrainer:
    """Fake trainer plugin for testing."""

    def __init__(self, **cfg):
        """Initialize with config kwargs."""
        self.cfg = cfg

    def run(self, input_card, recipe):
        """Return a fake ModelCard, logging the call."""
        CALL_LOG.append("train")
        return _make_card(card_id="PLACEHOLDER", task="sft")


class FakeEvaluator:
    """Fake evaluator plugin for testing."""

    def __init__(self, **cfg):
        """Initialize with config kwargs."""
        self.cfg = cfg

    def run(self, input_card, recipe):
        """Return a fake ModelCard, logging the call."""
        CALL_LOG.append("eval")
        return _make_card(card_id="PLACEHOLDER", task="eval")


@pytest.fixture(autouse=True)
def _register_fakes():
    """Register fake plugins before each test and unregister after."""
    TRAINERS.register_module(name="fake_sft", module=FakeSFTTrainer, force=True)
    EVALUATORS.register_module(name="fake_eval", module=FakeEvaluator, force=True)
    yield
    TRAINERS.module_dict.pop("fake_sft", None)
    EVALUATORS.module_dict.pop("fake_eval", None)


@pytest.fixture(autouse=True)
def _reset_log():
    CALL_LOG.clear()
    yield
    CALL_LOG.clear()


def _write_recipe(tmp_path: Path) -> Path:
    """Write a minimal valid ExperimentRecipe YAML to tmp_path."""
    # Write tiny stage config files
    train_cfg = tmp_path / "train_cfg.yaml"
    train_cfg.write_text("lr: 0.0001\n")
    eval_cfg = tmp_path / "eval_cfg.yaml"
    eval_cfg.write_text("suite: tiny\n")

    # experiment_logger must live at the top level (outside the "recipe" section)
    # so that ExperimentRecipe.model_validate doesn't reject it as an extra field.
    recipe = {
        "recipe": {
            "recipe_id": "test_resume",
            "description": "resume test recipe",
            "scope": "single_repo",
            "schema_version": pet_schema.SCHEMA_VERSION,
            "stages": [
                {
                    "name": "train",
                    "component_registry": "trainers",
                    "component_type": "fake_sft",
                    "inputs": {},
                    "config_path": str(train_cfg),
                    "depends_on": [],
                },
                {
                    "name": "eval",
                    "component_registry": "evaluators",
                    "component_type": "fake_eval",
                    "inputs": {},
                    "config_path": str(eval_cfg),
                    "depends_on": ["train"],
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


def test_resume_skips_cached_stage(tmp_path):
    recipe_path = _write_recipe(tmp_path)
    cache_root = tmp_path / "cache"

    # 1st run: train + eval both execute
    card1 = pet_run(recipe_path, resume=True, cache_root=cache_root)
    assert CALL_LOG == ["train", "eval"]

    # 2nd run: both stages are cache hits, plugins never invoked
    CALL_LOG.clear()
    card2 = pet_run(recipe_path, resume=True, cache_root=cache_root)
    assert CALL_LOG == []
    assert card2.id == card1.id  # deterministic card_id


def test_no_resume_reruns_all(tmp_path):
    recipe_path = _write_recipe(tmp_path)
    cache_root = tmp_path / "cache"
    pet_run(recipe_path, resume=True, cache_root=cache_root)
    CALL_LOG.clear()
    pet_run(recipe_path, resume=False, cache_root=cache_root)
    assert CALL_LOG == ["train", "eval"]
