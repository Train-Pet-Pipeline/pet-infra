"""Recipe composition: load, override, validate, hash."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import yaml
from omegaconf import OmegaConf
from pet_schema import ExperimentRecipe


def compose_recipe(
    path: str | Path,
    overrides: Sequence[str] = (),
) -> tuple[ExperimentRecipe, dict, str]:
    """Load a yaml recipe, apply overrides, validate against ExperimentRecipe.

    Phase 1 scope: single-file yaml. Phase 3 will add Hydra defaults-list
    resolution and multi-repo config search paths.

    Args:
        path: Path to the recipe yaml file.
        overrides: Iterable of ``key.path=<yaml-literal>`` strings.

    Returns:
        Tuple ``(recipe, resolved_dict, config_sha)`` where ``config_sha`` is
        the sha256 of the resolved config's canonical JSON form.
    """
    cfg = OmegaConf.load(str(path))
    for ov in overrides:
        key, _, val = ov.partition("=")
        OmegaConf.update(cfg, key, yaml.safe_load(val))
    resolved = OmegaConf.to_container(cfg, resolve=True)
    assert isinstance(resolved, dict)
    recipe_section = resolved["recipe"] if "recipe" in resolved else resolved
    recipe = ExperimentRecipe.model_validate(recipe_section)
    config_sha = hashlib.sha256(
        json.dumps(resolved, sort_keys=True, default=str).encode()
    ).hexdigest()
    return recipe, resolved, config_sha
