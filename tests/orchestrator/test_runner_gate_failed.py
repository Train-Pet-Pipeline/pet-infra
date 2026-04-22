# tests/orchestrator/test_runner_gate_failed.py
"""Integration test: evaluator gate_status='failed' stops the DAG walk."""
from datetime import datetime
from pathlib import Path

import pet_schema
import pytest
import yaml
from pet_schema.model_card import ModelCard

from pet_infra.orchestrator.runner import GateFailedError, pet_run
from pet_infra.registry import CONVERTERS, EVALUATORS, TRAINERS

CALL_LOG: list[str] = []


def _make_card(card_id: str, task: str, gate_status: str = "pending") -> ModelCard:
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
        metrics={"acc": 0.1},
        gate_status=gate_status,
        trained_at=datetime.utcnow(),
        trained_by="test",
    )


class GateTrainer:
    """Fake trainer for gate test."""

    def __init__(self, **cfg):
        """Initialize with config kwargs."""
        self.cfg = cfg

    def run(self, input_card, recipe):
        """Return a fake passed card."""
        CALL_LOG.append("train")
        return _make_card(card_id="PLACEHOLDER", task="sft", gate_status="pending")


class GateEvalFail:
    """Fake evaluator that returns gate_status='failed'."""

    def __init__(self, **cfg):
        """Initialize with config kwargs."""
        self.cfg = cfg

    def run(self, input_card, recipe):
        """Return a card with gate_status='failed'."""
        CALL_LOG.append("eval")
        return _make_card(card_id="PLACEHOLDER", task="eval", gate_status="failed")


class GateQuantize:
    """Fake converter — should NEVER be called when gate fails."""

    def __init__(self, **cfg):
        """Initialize with config kwargs."""
        self.cfg = cfg

    def run(self, input_card, recipe):
        """Record call and return card."""
        CALL_LOG.append("quantize")
        return _make_card(card_id="PLACEHOLDER", task="quantize")


@pytest.fixture(autouse=True)
def _register_fakes():
    """Register fake plugins before each test and unregister after."""
    TRAINERS.register_module(name="gate_train", module=GateTrainer, force=True)
    EVALUATORS.register_module(name="gate_eval_fail", module=GateEvalFail, force=True)
    CONVERTERS.register_module(name="gate_quantize", module=GateQuantize, force=True)
    yield
    TRAINERS.module_dict.pop("gate_train", None)
    EVALUATORS.module_dict.pop("gate_eval_fail", None)
    CONVERTERS.module_dict.pop("gate_quantize", None)


@pytest.fixture(autouse=True)
def _reset_log():
    CALL_LOG.clear()
    yield
    CALL_LOG.clear()


def _write_gate_recipe(tmp_path: Path) -> Path:
    """Write a recipe: train → eval (gate fails) → quantize."""
    train_cfg = tmp_path / "train_cfg.yaml"
    train_cfg.write_text("lr: 0.0001\n")
    eval_cfg = tmp_path / "eval_cfg.yaml"
    eval_cfg.write_text("suite: tiny\n")
    quantize_cfg = tmp_path / "quantize_cfg.yaml"
    quantize_cfg.write_text("bits: 4\n")

    recipe = {
        "recipe": {
            "recipe_id": "test_gate",
            "description": "gate short-circuit test",
            "scope": "single_repo",
            "schema_version": pet_schema.SCHEMA_VERSION,
            "stages": [
                {
                    "name": "train",
                    "component_registry": "trainers",
                    "component_type": "gate_train",
                    "inputs": {},
                    "config_path": str(train_cfg),
                    "depends_on": [],
                },
                {
                    "name": "eval",
                    "component_registry": "evaluators",
                    "component_type": "gate_eval_fail",
                    "inputs": {},
                    "config_path": str(eval_cfg),
                    "depends_on": ["train"],
                },
                {
                    "name": "quantize",
                    "component_registry": "converters",
                    "component_type": "gate_quantize",
                    "inputs": {},
                    "config_path": str(quantize_cfg),
                    "depends_on": ["eval"],
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


def test_gate_failed_short_circuits_downstream(tmp_path):
    """GateFailedError is raised; quantize never called; eval card saved to cache."""
    recipe_path = _write_gate_recipe(tmp_path)
    cache_root = tmp_path / "cache"

    with pytest.raises(GateFailedError):
        pet_run(recipe_path, resume=True, cache_root=cache_root)

    # train and eval ran; quantize did NOT
    assert CALL_LOG == ["train", "eval"]
    assert "quantize" not in CALL_LOG

    # eval card IS saved to cache (gate failed card persisted for inspection)
    from types import SimpleNamespace

    import yaml as _yaml

    from pet_infra.compose import compose_recipe
    from pet_infra.orchestrator.cache import StageCache
    from pet_infra.orchestrator.hash import hash_stage_config
    from pet_infra.recipe.card_id import precompute_card_id

    recipe_obj, _, _ = compose_recipe(recipe_path)
    eval_stage = next(s for s in recipe_obj.stages if s.name == "eval")

    # Reconstruct the same card_id the runner used
    train_stage = next(s for s in recipe_obj.stages if s.name == "train")
    train_cfg_dict = _yaml.safe_load(Path(train_stage.config_path).read_text()) or {}
    train_sha = hash_stage_config(SimpleNamespace(config=train_cfg_dict), None)
    train_card_id = precompute_card_id(recipe_obj.recipe_id, "train", train_sha)

    cache = StageCache(root=cache_root)
    train_cached = cache.load(train_card_id)
    assert train_cached is not None, "train card should be cached"

    train_card_ns = SimpleNamespace(checkpoint_uri=train_cached["checkpoint_uri"])
    eval_cfg_dict = _yaml.safe_load(Path(eval_stage.config_path).read_text()) or {}
    eval_sha = hash_stage_config(SimpleNamespace(config=eval_cfg_dict), train_card_ns)
    eval_card_id = precompute_card_id(recipe_obj.recipe_id, "eval", eval_sha)

    eval_cached = cache.load(eval_card_id)
    assert eval_cached is not None, "eval card should be cached even though gate failed"
    assert eval_cached["gate_status"] == "failed"
