"""Stage runners added in Phase 3B for CONVERTERS / DATASETS / OTA registries.

Each runner class exposes `.run(stage, input_card, recipe) -> ModelCard` and is
dispatched by ``stage_executor.STAGE_RUNNERS`` keyed on ``stage.component_registry``.
"""
from __future__ import annotations

from typing import Any

from omegaconf import OmegaConf
from pet_schema import ExperimentRecipe
from pet_schema.model_card import ModelCard

from pet_infra.registry import CONVERTERS, DATASETS, EVALUATORS, OTA, TRAINERS


class GateFailedError(Exception):
    """Raised by OtaStageRunner when upstream gate did not pass."""


def _load_stage_kwargs(stage: Any) -> dict:
    """Load plugin kwargs for a stage.

    Checks ``stage.config`` first (pre-loaded dict injected by the orchestrator),
    then falls back to loading ``stage.config_path`` from disk if present.
    This lets the same Runner serve both the orchestrator (pre-loaded config)
    and direct unit-test paths (config_path=None → empty dict).

    Args:
        stage: Any object with optional ``.config`` and/or ``.config_path`` attrs.

    Returns:
        Dict of kwargs to pass to the plugin constructor.
    """
    # Prefer pre-loaded config dict (injected by runner._StageWithConfig)
    pre_loaded = getattr(stage, "config", None)
    if pre_loaded is not None:
        return dict(pre_loaded)
    # Fall back to loading from disk via OmegaConf
    config_path = getattr(stage, "config_path", None)
    if not config_path:
        return {}
    cfg = OmegaConf.load(config_path)
    return OmegaConf.to_container(cfg, resolve=True) or {}  # type: ignore[return-value]


class TrainerStageRunner:
    """Dispatched for stage.component_registry == 'trainers'."""

    def run(self, stage: Any, input_card: ModelCard,
            recipe: ExperimentRecipe) -> ModelCard:
        """Instantiate a TRAINERS plugin and call its .run()."""
        plugin_cls = TRAINERS.get(stage.component_type)
        if plugin_cls is None:
            raise LookupError(
                f"TRAINERS['{stage.component_type}'] not registered")
        kwargs = _load_stage_kwargs(stage)
        plugin = plugin_cls(**kwargs)
        return plugin.run(input_card, recipe)


class EvaluatorStageRunner:
    """Dispatched for stage.component_registry == 'evaluators'."""

    def run(self, stage: Any, input_card: ModelCard,
            recipe: ExperimentRecipe) -> ModelCard:
        """Instantiate an EVALUATORS plugin and call its .run()."""
        plugin_cls = EVALUATORS.get(stage.component_type)
        if plugin_cls is None:
            raise LookupError(
                f"EVALUATORS['{stage.component_type}'] not registered")
        kwargs = _load_stage_kwargs(stage)
        plugin = plugin_cls(**kwargs)
        return plugin.run(input_card, recipe)


class ConverterStageRunner:
    """Dispatched for stage.component_registry == 'converters'."""

    def run(self, stage: Any, input_card: ModelCard,
            recipe: ExperimentRecipe) -> ModelCard:
        """Instantiate a CONVERTERS plugin and call its .run()."""
        plugin_cls = CONVERTERS.get(stage.component_type)
        if plugin_cls is None:
            raise LookupError(
                f"CONVERTERS['{stage.component_type}'] not registered")
        kwargs = _load_stage_kwargs(stage)
        plugin = plugin_cls(**kwargs)
        return plugin.run(input_card, recipe)


class DatasetStageRunner:
    """Dispatched for stage.component_registry == 'datasets'."""

    def run(self, stage: Any, input_card: ModelCard,
            recipe: ExperimentRecipe) -> ModelCard:
        """Instantiate a DATASETS plugin and call its .run()."""
        plugin_cls = DATASETS.get(stage.component_type)
        if plugin_cls is None:
            raise LookupError(
                f"DATASETS['{stage.component_type}'] not registered")
        kwargs = _load_stage_kwargs(stage)
        plugin = plugin_cls(**kwargs)
        return plugin.run(input_card, recipe)


class OtaStageRunner:
    """Dispatched for stage.component_registry == 'ota'.

    Guards gate_status == 'passed' before delegating to plugin.
    """

    def run(self, stage: Any, input_card: ModelCard,
            recipe: ExperimentRecipe) -> ModelCard:
        """Check gate then instantiate an OTA plugin and call its .run().

        Raises:
            GateFailedError: If ``input_card.gate_status != 'passed'``.
            LookupError: If the plugin is not registered in OTA.
        """
        if input_card.gate_status != "passed":
            raise GateFailedError(
                f"OTA stage blocked: gate_status={input_card.gate_status!r}")
        plugin_cls = OTA.get(stage.component_type)
        if plugin_cls is None:
            raise LookupError(
                f"OTA['{stage.component_type}'] not registered")
        kwargs = _load_stage_kwargs(stage)
        plugin = plugin_cls(**kwargs)
        return plugin.run(input_card, recipe)


# ---------------------------------------------------------------------------
# Dispatch map: component_registry → runner instance
# ---------------------------------------------------------------------------
STAGE_RUNNERS: dict[str, TrainerStageRunner | EvaluatorStageRunner
                    | ConverterStageRunner | DatasetStageRunner | OtaStageRunner] = {
    "trainers": TrainerStageRunner(),
    "evaluators": EvaluatorStageRunner(),
    "converters": ConverterStageRunner(),
    "datasets": DatasetStageRunner(),
    "ota": OtaStageRunner(),
}
