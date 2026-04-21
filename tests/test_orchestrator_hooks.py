"""Tests for Phase 3B stage runner hooks (Converter / Dataset / Ota)."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from pet_infra.orchestrator.hooks import (
    ConverterStageRunner,
    DatasetStageRunner,
    GateFailedError,
    OtaStageRunner,
)
from pet_infra.registry import CONVERTERS, DATASETS, OTA


def _make_card(gate_status: str = "passed"):
    """Create a minimal valid ModelCard for testing."""
    from pet_schema.model_card import ModelCard

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


@pytest.fixture
def minimal_card():
    """Minimal valid ModelCard with gate_status='passed'."""
    return _make_card(gate_status="passed")


def test_converter_runner_calls_plugin(minimal_card):
    """ConverterStageRunner dispatches to the registered plugin."""

    @CONVERTERS.register_module(name="_test_dummy_conv")
    class DummyConverter:
        """Dummy converter for test."""

        def __init__(self, **kwargs):
            """Init."""

        def run(self, input_card, recipe):
            """Return card with notes set."""
            return input_card.model_copy(update={"notes": "converter_ran"})

    try:
        stage = MagicMock(component_type="_test_dummy_conv", config_path=None)
        runner = ConverterStageRunner()
        out_card = runner.run(stage, minimal_card, recipe=MagicMock())
        assert out_card.notes == "converter_ran"
    finally:
        CONVERTERS._module_dict.pop("_test_dummy_conv", None)


def test_dataset_runner_calls_plugin(minimal_card):
    """DatasetStageRunner dispatches to the registered plugin."""

    @DATASETS.register_module(name="_test_dummy_ds")
    class DummyDataset:
        """Dummy dataset for test."""

        def __init__(self, **kwargs):
            """Init."""

        def run(self, input_card, recipe):
            """Return card with notes set."""
            return input_card.model_copy(update={"notes": "dataset_ran"})

    try:
        stage = MagicMock(component_type="_test_dummy_ds", config_path=None)
        runner = DatasetStageRunner()
        out_card = runner.run(stage, minimal_card, recipe=MagicMock())
        assert out_card.notes == "dataset_ran"
    finally:
        DATASETS._module_dict.pop("_test_dummy_ds", None)


def test_ota_runner_gate_guard_blocks_failed(minimal_card):
    """OtaStageRunner raises GateFailedError when gate_status != 'passed'."""

    @OTA.register_module(name="_test_dummy_ota")
    class DummyOta:
        """Dummy OTA for test."""

        def __init__(self, **kwargs):
            """Init."""

        def run(self, input_card, recipe):
            """Return card with notes set."""
            return input_card.model_copy(update={"notes": "ota_ran"})

    try:
        failed_card = minimal_card.model_copy(update={"gate_status": "failed"})
        stage = MagicMock(component_type="_test_dummy_ota", config_path=None)
        runner = OtaStageRunner()
        with pytest.raises(GateFailedError):
            runner.run(stage, failed_card, recipe=MagicMock())
    finally:
        OTA._module_dict.pop("_test_dummy_ota", None)


def test_ota_runner_happy_path(minimal_card):
    """OtaStageRunner calls plugin when gate_status == 'passed'."""

    @OTA.register_module(name="_test_dummy_ota2")
    class DummyOta2:
        """Dummy OTA for happy path test."""

        def __init__(self, **kwargs):
            """Init."""

        def run(self, input_card, recipe):
            """Return card with notes set."""
            return input_card.model_copy(update={"notes": "ota_ran"})

    try:
        stage = MagicMock(component_type="_test_dummy_ota2", config_path=None)
        runner = OtaStageRunner()
        out_card = runner.run(stage, minimal_card, recipe=MagicMock())
        assert out_card.notes == "ota_ran"
    finally:
        OTA._module_dict.pop("_test_dummy_ota2", None)


def test_ota_runner_gate_guard_blocks_pending(minimal_card):
    """OtaStageRunner raises GateFailedError when gate_status == 'pending'."""
    pending_card = minimal_card.model_copy(update={"gate_status": "pending"})
    stage = MagicMock(component_type="_no_plugin_needed", config_path=None)
    runner = OtaStageRunner()
    with pytest.raises(GateFailedError):
        runner.run(stage, pending_card, recipe=MagicMock())


def test_converter_runner_raises_on_unregistered(minimal_card):
    """ConverterStageRunner raises LookupError for unknown component_type."""
    stage = MagicMock(component_type="_not_registered_xyz", config_path=None)
    runner = ConverterStageRunner()
    with pytest.raises(LookupError):
        runner.run(stage, minimal_card, recipe=MagicMock())


def test_ota_registry_exported():
    """OTA registry is importable from pet_infra.registry."""
    from pet_infra.registry import OTA  # noqa: F401 — just check importable

    assert OTA is not None
