"""Top-level recipe composition with Hydra defaults-list resolution.

Canonical entry point for recipe composition. Previously split across
``compose.py`` (simple path) and ``recipe/compose.py`` (full path with
overrides + sha); merged here to a single source of truth.

Phase 3B: adds ``defaults: [base_a, sub/override]`` support relative to the
recipe file's directory. Later entries override earlier ones; the top-level
file overrides all defaults. Circular chains raise ComposeError.

Legacy recipes without a ``defaults:`` key work unchanged (backward compat).
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import yaml
from omegaconf import DictConfig, ListConfig, OmegaConf
from pet_schema import ExperimentRecipe


class ComposeError(Exception):
    """Raised when recipe composition fails (circular chain, missing target, etc.)."""


def _resolve_defaults(recipe_path: Path, visited: set[Path] | None = None) -> DictConfig:
    """Recursively resolve ``defaults:`` list relative to recipe_path.parent.

    Later entries override earlier; top-level file overrides all defaults.
    Circular chains raise ComposeError.

    Args:
        recipe_path: Absolute path to the yaml file to resolve.
        visited: Set of already-visited paths for cycle detection.

    Returns:
        Merged DictConfig with defaults resolved and the ``defaults`` key removed.

    Raises:
        ComposeError: On circular chains or missing targets.
    """
    if visited is None:
        visited = set()
    recipe_path = recipe_path.resolve()
    if recipe_path in visited:
        raise ComposeError(f"circular defaults chain through {recipe_path}")
    visited = visited | {recipe_path}
    if not recipe_path.exists():
        raise ComposeError(f"defaults target not found: {recipe_path}")
    raw: DictConfig | ListConfig = OmegaConf.load(recipe_path)
    defaults_list = raw.pop("defaults", []) if isinstance(raw, DictConfig) else []
    merged: DictConfig | ListConfig = OmegaConf.create({})
    base_dir = recipe_path.parent
    for entry in defaults_list:
        if not isinstance(entry, str):
            raise ComposeError(f"defaults entries must be strings, got {entry!r}")
        target = base_dir / (entry if entry.endswith(".yaml") else f"{entry}.yaml")
        sub = _resolve_defaults(target, visited)
        merged = OmegaConf.merge(merged, sub)
    merged = OmegaConf.merge(merged, raw)
    assert isinstance(merged, DictConfig)
    return merged


def compose_recipe(
    path: str | Path,
    overrides: Sequence[str] = (),
) -> tuple[ExperimentRecipe, dict, str]:
    """Load a yaml recipe, resolve defaults-list, apply overrides, validate.

    Supports Phase 3B Hydra-style ``defaults: [base_a, sub/override]`` lists
    resolved relative to the recipe file's directory (via
    ``_resolve_defaults``). Also strips compose-time interpolation variables
    (e.g. ``smoke_tier``) and normalises dict-keyed stages to the
    ``list[RecipeStage]`` form Pydantic requires.

    Legacy single-file recipes without ``defaults:`` work unchanged.

    Args:
        path: Path to the recipe yaml file.
        overrides: Iterable of ``key.path=<yaml-literal>`` strings.

    Returns:
        Tuple ``(recipe, resolved_dict, config_sha)`` where ``config_sha`` is
        the sha256 of the resolved config's canonical JSON form.

    Raises:
        ComposeError: On circular chains or missing defaults targets.
        pydantic.ValidationError: On schema validation failure.
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
