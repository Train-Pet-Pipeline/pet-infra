"""Tests for Phase 3B fragment-composed recipes.

Note: compose_recipe() validates recipe structure only; per-stage config files
(configs/smoke/*.yaml) are loaded lazily by the orchestrator, so their absence
here is expected and intentional.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pet_infra.compose import compose_recipe

RECIPES = Path(__file__).parent.parent / "recipes"


@pytest.mark.parametrize("recipe_name", ["smoke_tiny", "smoke_mps", "smoke_small", "release"])
def test_phase3b_recipe_composes(recipe_name: str) -> None:
    """Each Phase 3B recipe must compose to a valid ExperimentRecipe."""
    recipe = compose_recipe(RECIPES / f"{recipe_name}.yaml")
    assert recipe.recipe_id == recipe_name
    assert len(recipe.stages) >= 2
    valid_registries = {"trainers", "evaluators", "converters", "datasets", "ota"}
    for stage in recipe.stages:
        assert stage.component_registry in valid_registries


def test_release_recipe_has_deploy_stage() -> None:
    """Release recipe must contain a deploy stage."""
    recipe = compose_recipe(RECIPES / "release.yaml")
    stage_names = {s.name for s in recipe.stages}
    assert "deploy" in stage_names


def test_smoke_tiny_has_minimal_dag() -> None:
    """smoke_tiny skips eval_quant and calibrate; has train → quantize → deploy."""
    recipe = compose_recipe(RECIPES / "smoke_tiny.yaml")
    stage_names = {s.name for s in recipe.stages}
    assert "eval_quant" not in stage_names
    assert "calibrate" not in stage_names
    assert {"train", "quantize", "deploy"}.issubset(stage_names)


def test_smoke_mps_has_full_dag() -> None:
    """smoke_mps has all 6 pipeline stages."""
    recipe = compose_recipe(RECIPES / "smoke_mps.yaml")
    stage_names = {s.name for s in recipe.stages}
    full_dag = {"train", "eval_fp", "calibrate", "quantize", "eval_quant", "deploy"}
    assert full_dag.issubset(stage_names)


def test_smoke_tiny_deploy_depends_on_quantize() -> None:
    """smoke_tiny deploy stage must depend on quantize, not eval_quant."""
    recipe = compose_recipe(RECIPES / "smoke_tiny.yaml")
    deploy = next(s for s in recipe.stages if s.name == "deploy")
    assert deploy.depends_on == ["quantize"]


def test_recipes_scope_values() -> None:
    """Verify scope field values for all Phase 3B recipes."""
    expected = {
        "smoke_tiny": "single_repo",
        "smoke_mps": "cross_repo",
        "smoke_small": "cross_repo",
        "release": "cross_repo",
    }
    for name, scope in expected.items():
        recipe = compose_recipe(RECIPES / f"{name}.yaml")
        assert recipe.scope == scope, f"{name} scope mismatch"
