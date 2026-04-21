"""Top-level recipe composition with Hydra defaults-list resolution.

Phase 3B: adds ``defaults: [base_a, sub/override]`` support relative to the
recipe file's directory. Later entries override earlier ones; the top-level
file overrides all defaults. Circular chains raise ComposeError.

Legacy recipes without a ``defaults:`` key work unchanged (backward compat).
"""
from __future__ import annotations

from pathlib import Path

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


def compose_recipe(path: str | Path) -> ExperimentRecipe:
    """Load a yaml recipe, resolve any defaults: list, and validate.

    Supports Hydra-style ``defaults: [base_a, sub/override]`` lists resolved
    relative to the recipe file's directory. Recipes without a ``defaults:``
    key work unchanged (backward compat with Phase 3A).

    For recipes that wrap fields under a ``recipe:`` top-level key (e.g.
    Phase 3A smoke recipes), the ``recipe:`` section is unwrapped before
    validation.

    Args:
        path: Path to the recipe yaml file.

    Returns:
        Validated ExperimentRecipe instance.

    Raises:
        ComposeError: On circular chains or missing defaults targets.
        pydantic.ValidationError: On schema validation failure.
    """
    cfg = _resolve_defaults(Path(path))
    resolved = OmegaConf.to_container(cfg, resolve=True)
    assert isinstance(resolved, dict)
    recipe_section = resolved["recipe"] if "recipe" in resolved else resolved
    # Phase 3B: strip compose-time variables (e.g. smoke_tier) that are not
    # ExperimentRecipe fields — these are used for OmegaConf interpolation only
    # and must not be passed to Pydantic (extra='forbid').
    known_fields = set(ExperimentRecipe.model_fields)
    recipe_section = {k: v for k, v in recipe_section.items() if k in known_fields}
    # Phase 3B: fragments use dict-keyed stages so OmegaConf can deep-merge them.
    # Convert dict[str, dict] → list[dict] with `name` injected from the key
    # before passing to Pydantic (which requires list[RecipeStage]).
    if isinstance(recipe_section.get("stages"), dict):
        recipe_section["stages"] = [
            {"name": name, **body} for name, body in recipe_section["stages"].items()
        ]
    return ExperimentRecipe.model_validate(recipe_section)
