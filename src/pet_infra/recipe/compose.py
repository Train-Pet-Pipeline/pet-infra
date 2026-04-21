"""Recipe composition: load, override, validate, hash."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import yaml
from omegaconf import OmegaConf
from pet_schema import ExperimentRecipe

from pet_infra.compose import _resolve_defaults


def compose_recipe(
    path: str | Path,
    overrides: Sequence[str] = (),
) -> tuple[ExperimentRecipe, dict, str]:
    """Load a yaml recipe, resolve defaults-list, apply overrides, validate.

    Supports Phase 3B Hydra-style ``defaults: [base_a, sub/override]`` lists
    resolved relative to the recipe file's directory (delegates to
    ``pet_infra.compose._resolve_defaults``). Also strips compose-time
    interpolation variables (e.g. ``smoke_tier``) and normalises dict-keyed
    stages to the ``list[RecipeStage]`` form Pydantic requires.

    Legacy single-file recipes without ``defaults:`` work unchanged.

    Args:
        path: Path to the recipe yaml file.
        overrides: Iterable of ``key.path=<yaml-literal>`` strings.

    Returns:
        Tuple ``(recipe, resolved_dict, config_sha)`` where ``config_sha`` is
        the sha256 of the resolved config's canonical JSON form.
    """
    # Phase 3B: use _resolve_defaults for defaults-list support; falls back
    # gracefully for legacy recipes that have no defaults: key.
    cfg = _resolve_defaults(Path(path))
    for ov in overrides:
        key, _, val = ov.partition("=")
        OmegaConf.update(cfg, key, yaml.safe_load(val))
    resolved = OmegaConf.to_container(cfg, resolve=True)
    assert isinstance(resolved, dict)
    recipe_section = resolved["recipe"] if "recipe" in resolved else resolved
    # Strip compose-time variables (e.g. smoke_tier) not in ExperimentRecipe schema.
    known_fields = set(ExperimentRecipe.model_fields)
    recipe_section = {k: v for k, v in recipe_section.items() if k in known_fields}
    # Normalise dict-keyed stages → list[RecipeStage] (Phase 3B fragment style).
    if isinstance(recipe_section.get("stages"), dict):
        recipe_section["stages"] = [
            {"name": name, **body} for name, body in recipe_section["stages"].items()
        ]
    recipe = ExperimentRecipe.model_validate(recipe_section)
    config_sha = hashlib.sha256(
        json.dumps(resolved, sort_keys=True, default=str).encode()
    ).hexdigest()
    return recipe, resolved, config_sha
