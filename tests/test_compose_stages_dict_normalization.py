"""Regression test: compose.py normalizes dict-keyed stages to list for Pydantic.

Phase 3B fragments use dict-keyed stages so OmegaConf deep-merge works
correctly across fragments. compose_recipe() must convert these to the
list[RecipeStage] form that ExperimentRecipe requires.
"""
from __future__ import annotations

from pathlib import Path

from pet_infra.compose import compose_recipe


def test_stages_dict_is_normalized_to_list(tmp_path: Path) -> None:
    """Dict-keyed stages must be normalized to an ordered list by compose_recipe."""
    recipe_yaml = tmp_path / "r.yaml"
    recipe_yaml.write_text(
        """
recipe_id: test
description: dict-stages normalization
scope: single_repo
schema_version: "2.0.0"
stages:
  train:
    component_registry: trainers
    component_type: tiny_test
    inputs: {}
    config_path: configs/x.yaml
    depends_on: []
  eval:
    component_registry: evaluators
    component_type: vlm_evaluator
    inputs: {}
    config_path: configs/y.yaml
    depends_on: [train]
variations: []
produces: [out]
default_storage: local
required_plugins: []
"""
    )
    recipe, _, _ = compose_recipe(recipe_yaml)
    stage_names = [s.name for s in recipe.stages]
    assert stage_names == ["train", "eval"]


def test_stages_dict_preserves_stage_fields(tmp_path: Path) -> None:
    """Normalized stages must retain all original field values."""
    recipe_yaml = tmp_path / "r2.yaml"
    recipe_yaml.write_text(
        """
recipe_id: test2
description: field preservation
scope: single_repo
schema_version: "2.0.0"
stages:
  quantize:
    component_registry: converters
    component_type: noop_converter
    inputs: {}
    config_path: configs/q.yaml
    depends_on: [train]
    on_failure: continue
variations: []
produces: [out]
default_storage: local
required_plugins: []
"""
    )
    recipe, _, _ = compose_recipe(recipe_yaml)
    assert len(recipe.stages) == 1
    stage = recipe.stages[0]
    assert stage.name == "quantize"
    assert stage.component_registry == "converters"
    assert stage.component_type == "noop_converter"
    assert stage.depends_on == ["train"]
    assert stage.on_failure == "continue"


def test_stages_list_unchanged(tmp_path: Path) -> None:
    """Recipes already using list-form stages must not be affected (backward compat)."""
    recipe_yaml = tmp_path / "r3.yaml"
    recipe_yaml.write_text(
        """
recipe_id: test3
description: list stages unchanged
scope: single_repo
schema_version: "2.0.0"
stages:
  - name: train
    component_registry: trainers
    component_type: tiny_test
    inputs: {}
    config_path: configs/t.yaml
    depends_on: []
variations: []
produces: [out]
default_storage: local
required_plugins: []
"""
    )
    recipe, _, _ = compose_recipe(recipe_yaml)
    assert [s.name for s in recipe.stages] == ["train"]
