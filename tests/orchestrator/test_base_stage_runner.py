"""Base stage runner tests — verify common lookup + instantiation + run behavior."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from pet_schema.model_card import ModelCard


def _make_card(gate_status: str = "passed") -> ModelCard:
    """Create a minimal valid ModelCard for testing."""
    return ModelCard(
        id="abc",
        version="0.1.0",
        modality="vision",
        task="sft",
        arch="fake",
        training_recipe="r",
        hydra_config_sha="s" * 40,
        git_shas={},
        dataset_versions={},
        checkpoint_uri="/tmp/ckpt",
        metrics={"acc": 0.1},
        gate_status=gate_status,
        trained_at=datetime.utcnow(),
        trained_by="test",
    )


class TestBaseStageRunner:
    """Tests for BaseStageRunner — the extracted common base."""

    def test_base_stage_runner_is_importable(self):
        """BaseStageRunner is exported from hooks module."""
        from pet_infra.orchestrator.hooks import BaseStageRunner  # noqa: F401

        assert BaseStageRunner is not None

    def test_base_stage_runner_looks_up_plugin_by_component_type(self):
        """BaseStageRunner.run resolves plugin via registry.get()."""
        from pet_infra.orchestrator.hooks import BaseStageRunner

        mock_registry = MagicMock()
        mock_plugin_instance = MagicMock()
        mock_plugin_cls = MagicMock(return_value=mock_plugin_instance)
        mock_registry.get.return_value = mock_plugin_cls

        class TestRunner(BaseStageRunner):
            registry = mock_registry
            _registry_label = "TEST"

        card = _make_card()
        stage = MagicMock(component_type="my_plugin", config_path=None)
        stage.config = None
        recipe = MagicMock()

        TestRunner().run(stage, card, recipe)

        mock_registry.get.assert_called_once_with("my_plugin")

    def test_base_stage_runner_instantiates_and_calls_plugin(self):
        """Plugin is instantiated with stage kwargs; run() delegates to plugin.run()."""
        from pet_infra.orchestrator.hooks import BaseStageRunner

        mock_plugin_instance = MagicMock()
        expected_result = _make_card()
        mock_plugin_instance.run.return_value = expected_result
        mock_plugin_cls = MagicMock(return_value=mock_plugin_instance)
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_plugin_cls

        class TestRunner(BaseStageRunner):
            registry = mock_registry
            _registry_label = "TEST"

        card = _make_card()
        stage = MagicMock(component_type="my_plugin", config_path=None)
        stage.config = None
        recipe = MagicMock()

        result = TestRunner().run(stage, card, recipe)

        mock_plugin_cls.assert_called_once_with()  # no kwargs since config=None
        mock_plugin_instance.run.assert_called_once_with(card, recipe)
        assert result is expected_result

    def test_base_stage_runner_raises_lookup_error_when_plugin_not_registered(self):
        """Missing plugin → LookupError with registry label + component_type context."""
        from pet_infra.orchestrator.hooks import BaseStageRunner

        mock_registry = MagicMock()
        mock_registry.get.return_value = None

        class TestRunner(BaseStageRunner):
            registry = mock_registry
            _registry_label = "MYREG"

        card = _make_card()
        stage = MagicMock(component_type="no_such_plugin", config_path=None)
        stage.config = None

        with pytest.raises(LookupError, match="MYREG\\['no_such_plugin'\\] not registered"):
            TestRunner().run(stage, card, MagicMock())

    def test_base_stage_runner_passes_kwargs_to_plugin(self):
        """Plugin is instantiated with kwargs from stage.config."""
        from pet_infra.orchestrator.hooks import BaseStageRunner

        captured = {}
        mock_plugin_instance = MagicMock()
        mock_plugin_instance.run.return_value = _make_card()

        def capture_cls(**kwargs):
            captured.update(kwargs)
            return mock_plugin_instance

        mock_registry = MagicMock()
        mock_registry.get.return_value = capture_cls

        class TestRunner(BaseStageRunner):
            registry = mock_registry
            _registry_label = "TEST"

        card = _make_card()
        stage = MagicMock(component_type="my_plugin")
        stage.config = {"lr": 0.001, "epochs": 3}

        TestRunner().run(stage, card, MagicMock())

        assert captured == {"lr": 0.001, "epochs": 3}

    def test_trivial_subclasses_use_correct_registries(self):
        """TrainerStageRunner, EvaluatorStageRunner, ConverterStageRunner, DatasetStageRunner
        each reference the correct registry constant."""
        from pet_infra.orchestrator.hooks import (
            ConverterStageRunner,
            DatasetStageRunner,
            EvaluatorStageRunner,
            TrainerStageRunner,
        )
        from pet_infra.registry import CONVERTERS, DATASETS, EVALUATORS, TRAINERS

        assert TrainerStageRunner.registry is TRAINERS
        assert EvaluatorStageRunner.registry is EVALUATORS
        assert ConverterStageRunner.registry is CONVERTERS
        assert DatasetStageRunner.registry is DATASETS
