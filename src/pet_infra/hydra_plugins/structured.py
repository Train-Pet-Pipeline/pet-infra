"""Hydra ConfigStore registration for pet-schema config groups.

Uses hydra-zen ``builds(ModelCls, populate_full_signature=True)`` to
auto-generate Hydra-compatible structured configs from pet-schema's
Pydantic v2 BaseModel types. This preserves pet-schema as the single
source of truth for field definitions — no manual dataclass mirrors,
no drift risk — while exposing Hydra-native field-level types for
config composition and ``hydra.utils.instantiate`` resolution.

Registered groups (each with name ``base``):
  - recipe    → ExperimentRecipe
  - trainer   → TrainerConfig
  - evaluator → EvaluatorConfig
  - converter → ConverterConfig
  - dataset   → DatasetConfig
"""
from __future__ import annotations

from hydra.core.config_store import ConfigStore
from hydra_zen import builds
from pet_schema import (
    ConverterConfig,
    DatasetConfig,
    EvaluatorConfig,
    ExperimentRecipe,
    TrainerConfig,
)

_GROUPS = {
    "recipe": ExperimentRecipe,
    "trainer": TrainerConfig,
    "evaluator": EvaluatorConfig,
    "converter": ConverterConfig,
    "dataset": DatasetConfig,
}


def register() -> None:
    """Register pet-schema structured configs with Hydra's ConfigStore.

    Uses hydra-zen ``builds()`` to auto-generate a dataclass mirror for each
    pet-schema Pydantic model. Each generated config carries a ``_target_``
    pointing at the corresponding pet-schema class, enabling
    ``hydra.utils.instantiate(cfg)`` to produce real Pydantic instances.
    """
    cs = ConfigStore.instance()
    for group, pydantic_cls in _GROUPS.items():
        node = builds(pydantic_cls, populate_full_signature=True)
        cs.store(group=group, name="base", node=node)
