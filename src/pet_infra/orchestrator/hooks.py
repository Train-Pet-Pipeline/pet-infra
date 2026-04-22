"""Stage runners added in Phase 3B for CONVERTERS / DATASETS / OTA registries.

Each runner class exposes `.run(stage, input_card, recipe) -> ModelCard` and is
dispatched by ``stage_executor.STAGE_RUNNERS`` keyed on ``stage.component_registry``.
"""
from __future__ import annotations

from typing import Any, ClassVar

from mmengine.registry import Registry
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


class BaseStageRunner:
    """Base stage runner — wraps registry lookup + plugin instantiation + run.

    Subclasses MUST set ``registry`` (ClassVar[Registry]) and ``_registry_label``
    (ClassVar[str], the uppercase variable name used in error messages).
    Subclasses MAY override ``run()`` for stage-type-specific behavior
    (e.g. OtaStageRunner's gate check).
    """

    registry: ClassVar[Registry]
    _registry_label: ClassVar[str]

    def run(self, stage: Any, input_card: ModelCard,
            recipe: ExperimentRecipe) -> ModelCard:
        """Instantiate a plugin from registry and call its .run().

        Args:
            stage: Stage config object with ``.component_type`` attr.
            input_card: Upstream ModelCard passed to the plugin.
            recipe: ExperimentRecipe passed to the plugin.

        Raises:
            LookupError: If the plugin is not registered.

        Returns:
            ModelCard produced by the plugin.
        """
        plugin_cls = self.registry.get(stage.component_type)
        if plugin_cls is None:
            raise LookupError(
                f"{self._registry_label}['{stage.component_type}'] not registered")
        kwargs = _load_stage_kwargs(stage)
        plugin = plugin_cls(**kwargs)
        return plugin.run(input_card, recipe)


class TrainerStageRunner(BaseStageRunner):
    """Dispatched for stage.component_registry == 'trainers'."""

    registry = TRAINERS
    _registry_label = "TRAINERS"


class EvaluatorStageRunner(BaseStageRunner):
    """Dispatched for stage.component_registry == 'evaluators'."""

    registry = EVALUATORS
    _registry_label = "EVALUATORS"


class ConverterStageRunner(BaseStageRunner):
    """Dispatched for stage.component_registry == 'converters'."""

    registry = CONVERTERS
    _registry_label = "CONVERTERS"


class DatasetStageRunner(BaseStageRunner):
    """Dispatched for stage.component_registry == 'datasets'."""

    registry = DATASETS
    _registry_label = "DATASETS"


class OtaStageRunner(BaseStageRunner):
    """Dispatched for stage.component_registry == 'ota'.

    Guards gate_status == 'passed' before delegating to plugin.
    """

    registry = OTA
    _registry_label = "OTA"

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
        return super().run(stage, input_card, recipe)


# ---------------------------------------------------------------------------
# Dispatch map: component_registry → runner instance
# ---------------------------------------------------------------------------
STAGE_RUNNERS: dict[str, BaseStageRunner] = {
    "trainers": TrainerStageRunner(),
    "evaluators": EvaluatorStageRunner(),
    "converters": ConverterStageRunner(),
    "datasets": DatasetStageRunner(),
    "ota": OtaStageRunner(),
}
