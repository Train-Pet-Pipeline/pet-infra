"""Hydra ConfigStore registration for pet-schema config groups.

Phase 1 scope: reserve group/name slots so recipes can use Hydra's
defaults-list composition. Field-level validation lives in pet-schema
(Pydantic) and fires in ``compose_recipe`` via ``model_validate`` — we
do not duplicate pet-schema fields as dataclasses to avoid drift.

Phase 3 will revisit if structured-config-level type hints become valuable.
"""
from __future__ import annotations

from dataclasses import dataclass

from hydra.core.config_store import ConfigStore


@dataclass
class _RecipeSlot:
    pass


@dataclass
class _TrainerSlot:
    pass


@dataclass
class _EvaluatorSlot:
    pass


@dataclass
class _ConverterSlot:
    pass


@dataclass
class _DatasetSlot:
    pass


def register() -> None:
    """Register pet-schema config group slots with Hydra's ConfigStore.

    Reserves group/name combinations so Phase 3 recipes can use Hydra's
    defaults-list composition syntax (``defaults: [trainer: base, ...]``).
    No pet-schema fields are duplicated here — validation fires in B7 via
    ``ExperimentRecipe.model_validate(resolved_dict)``.
    """
    cs = ConfigStore.instance()
    cs.store(group="recipe",    name="base", node=_RecipeSlot)
    cs.store(group="trainer",   name="base", node=_TrainerSlot)
    cs.store(group="evaluator", name="base", node=_EvaluatorSlot)
    cs.store(group="converter", name="base", node=_ConverterSlot)
    cs.store(group="dataset",   name="base", node=_DatasetSlot)
