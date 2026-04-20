"""Tests for build_execution_plan() — topological execution order helper."""
from __future__ import annotations

import pytest
from pet_schema import ExperimentRecipe
from pydantic import ValidationError

from pet_infra.recipe.dag import build_execution_plan


def _make_recipe(stages: list[dict]) -> ExperimentRecipe:
    """Build an ExperimentRecipe from a list of stage dicts."""
    return ExperimentRecipe.model_validate(
        {
            "recipe_id": "test-dag",
            "description": "DAG test recipe",
            "scope": "single_repo",
            "schema_version": "2.0.0",
            "stages": stages,
            "variations": [],
            "produces": ["final_artifact"],
            "default_storage": "local",
            "required_plugins": [],
        }
    )


def _stage(name: str, depends_on: list[str] | None = None) -> dict:
    return {
        "name": name,
        "component_registry": "trainers",
        "component_type": "sft_lora",
        "inputs": {},
        "config_path": f"configs/{name}.yaml",
        "depends_on": depends_on or [],
    }


class TestBuildExecutionPlan:
    """Tests for build_execution_plan()."""

    def test_returns_list_of_strings(self) -> None:
        """build_execution_plan returns a list of stage name strings."""
        recipe = _make_recipe([_stage("sft")])
        plan = build_execution_plan(recipe)
        assert isinstance(plan, list)
        assert all(isinstance(s, str) for s in plan)

    def test_six_stage_pipeline_respects_dependencies(self) -> None:
        """For a 6-stage pipeline the returned order satisfies all depends_on constraints."""
        stages = [
            _stage("distill"),
            _stage("sft", depends_on=["distill"]),
            _stage("dpo", depends_on=["sft"]),
            _stage("eval_trained", depends_on=["dpo"]),
            _stage("quantize", depends_on=["eval_trained"]),
            _stage("eval_quantized", depends_on=["quantize"]),
        ]
        recipe = _make_recipe(stages)
        plan = build_execution_plan(recipe)

        # All six stages must appear exactly once
        assert sorted(plan) == sorted(s["name"] for s in stages)

        # Every stage must appear after all its dependencies
        for stage in recipe.stages:
            stage_idx = plan.index(stage.name)
            for dep in stage.depends_on:
                assert plan.index(dep) < stage_idx, (
                    f"dependency '{dep}' should come before '{stage.name}' in plan"
                )

    def test_single_stage_recipe(self) -> None:
        """A single-stage recipe returns a plan with exactly that stage name."""
        recipe = _make_recipe([_stage("sft")])
        assert build_execution_plan(recipe) == ["sft"]

    def test_cyclic_recipe_raises_at_model_validate(self) -> None:
        """A recipe with a cycle raises ValidationError at model_validate time."""
        cyclic_stages = [
            _stage("a", depends_on=["b"]),
            _stage("b", depends_on=["a"]),
        ]
        raw = {
            "recipe_id": "cyclic",
            "description": "Cyclic recipe",
            "scope": "single_repo",
            "schema_version": "2.0.0",
            "stages": cyclic_stages,
            "variations": [],
            "produces": ["x"],
            "default_storage": "local",
            "required_plugins": [],
        }
        with pytest.raises(ValidationError):
            ExperimentRecipe.model_validate(raw)
