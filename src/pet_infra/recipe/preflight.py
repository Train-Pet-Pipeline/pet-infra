"""Fail-fast preflight validation for ExperimentRecipe instances."""
from __future__ import annotations

from urllib.parse import urlparse

from pet_schema import ExperimentRecipe

from pet_infra.registry import CONVERTERS, DATASETS, EVALUATORS, OTA, STORAGE, TRAINERS


class PreflightError(RuntimeError):
    """Raised when a recipe fails fail-fast validation before execution."""


_REGISTRY_BY_NAME = {
    "trainers": TRAINERS,
    "evaluators": EVALUATORS,
    "converters": CONVERTERS,
    "datasets": DATASETS,
    "ota": OTA,
}


def preflight(recipe: ExperimentRecipe) -> None:
    """Validate a recipe against the current plugin registry.

    Checks (Phase 1 scope):
      1. Each stage's ``component_type`` is registered in its ``component_registry``.
      2. Each ``dvc_path`` input URI's scheme is registered in ``STORAGE``.
         A bare path with no URI scheme defaults to ``"local"``.
      3. Each ``recipe_stage_output`` input points to a stage name that exists
         in the same recipe.

    DAG acyclicity is enforced by ``ExperimentRecipe``'s own model validator at
    ``model_validate()`` time; by the time a recipe instance is passed here the
    DAG is guaranteed to be acyclic, so no re-check is performed.

    External-system probes (ClearML / DVC / GPU availability) are deferred to
    Phase 3+ and are NOT part of this function.

    Args:
        recipe: A validated ``ExperimentRecipe`` instance.

    Returns:
        ``None`` when all checks pass.

    Raises:
        PreflightError: with a message identifying the offending stage / input.
    """
    stage_names = {s.name for s in recipe.stages}

    for stage in recipe.stages:
        # Check 1a — registry name must be known
        reg = _REGISTRY_BY_NAME.get(stage.component_registry)
        if reg is None:
            raise PreflightError(
                f"stage {stage.name!r}: unknown component_registry "
                f"{stage.component_registry!r}"
            )

        # Check 1b — component_type must be registered
        if stage.component_type not in reg.module_dict:
            raise PreflightError(
                f"stage {stage.name!r}: plugin {stage.component_type!r} "
                f"not registered in {stage.component_registry!r}"
            )

        for input_name, ref in stage.inputs.items():
            if ref.ref_type == "recipe_stage_output":
                # Check 3 — upstream stage must exist in this recipe
                if ref.ref_value not in stage_names:
                    raise PreflightError(
                        f"stage {stage.name!r}: input {input_name!r} points to "
                        f"unknown upstream stage {ref.ref_value!r}"
                    )
            elif ref.ref_type == "dvc_path":
                # Check 2 — storage scheme must be registered
                scheme = urlparse(ref.ref_value).scheme or "local"
                if scheme not in STORAGE.module_dict:
                    raise PreflightError(
                        f"stage {stage.name!r}: storage scheme {scheme!r} "
                        f"not registered"
                    )
