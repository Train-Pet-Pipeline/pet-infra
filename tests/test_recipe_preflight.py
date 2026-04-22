"""Tests for preflight() — fail-fast recipe validation."""
from __future__ import annotations

import pytest
from pet_schema import ExperimentRecipe

import pet_infra.storage.local  # noqa: F401 — registers "local" in STORAGE
from pet_infra.recipe.preflight import PreflightError, preflight
from pet_infra.registry import DATASETS, EVALUATORS, OTA, TRAINERS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE = {
    "recipe_id": "preflight-test",
    "description": "Preflight test recipe",
    "scope": "single_repo",
    "schema_version": "2.0.0",
    "variations": [],
    "produces": ["output"],
    "default_storage": "local",
    "required_plugins": [],
}


def _make_recipe(**stage_overrides: object) -> ExperimentRecipe:
    """Build a minimal valid ExperimentRecipe with one stage.

    Defaults: trainers registry, 'fake_trainer' component_type, no inputs.
    Pass kwargs to override any stage field.
    """
    stage = {
        "name": "train",
        "component_registry": "trainers",
        "component_type": "fake_trainer",
        "inputs": {},
        "config_path": "configs/train.yaml",
        "depends_on": [],
    }
    stage.update(stage_overrides)
    return ExperimentRecipe.model_validate({**_BASE, "stages": [stage]})


# ---------------------------------------------------------------------------
# Check 1 — component registration
# ---------------------------------------------------------------------------


class TestComponentRegistration:
    """preflight() check 1: component_type must be registered in component_registry."""

    def test_unregistered_trainer_raises(self) -> None:
        """Unregistered component_type in 'trainers' raises PreflightError."""
        recipe = _make_recipe(component_registry="trainers", component_type="__not_registered__")
        with pytest.raises(PreflightError, match=r"plugin '__not_registered__' not registered"):
            preflight(recipe)

    def test_unregistered_evaluator_raises(self) -> None:
        """Unregistered component_type in 'evaluators' raises PreflightError."""
        recipe = _make_recipe(
            component_registry="evaluators", component_type="__not_registered_eval__"
        )
        with pytest.raises(
            PreflightError, match=r"plugin '__not_registered_eval__' not registered"
        ):
            preflight(recipe)

    def test_registered_trainer_passes(self) -> None:
        """A registered component_type does NOT raise."""

        @TRAINERS.register_module(name="fake_trainer")
        class FakeTrainer:
            """Fake trainer for testing."""

        try:
            recipe = _make_recipe(component_registry="trainers", component_type="fake_trainer")
            result = preflight(recipe)
            assert result is None
        finally:
            TRAINERS._module_dict.pop("fake_trainer", None)


# ---------------------------------------------------------------------------
# Check 1b — unknown registry name
# ---------------------------------------------------------------------------


class TestUnknownRegistryName:
    """preflight() raises PreflightError for unknown component_registry values."""

    def test_unknown_registry_name_raises(self) -> None:
        """component_registry not in _REGISTRY_BY_NAME raises PreflightError."""
        # We must bypass pydantic's Literal validation to inject an invalid registry name.
        # Build a valid recipe, then monkey-patch the stage's component_registry field.
        @TRAINERS.register_module(name="fake_trainer")
        class FakeTrainer:
            """Fake trainer for testing."""

        try:
            recipe = _make_recipe(component_registry="trainers", component_type="fake_trainer")
            # Patch the stage object's field so preflight sees the bad registry name
            object.__setattr__(recipe.stages[0], "component_registry", "nonexistent_registry")
            with pytest.raises(PreflightError, match=r"unknown component_registry"):
                preflight(recipe)
        finally:
            TRAINERS._module_dict.pop("fake_trainer", None)


# ---------------------------------------------------------------------------
# Check 2 — storage scheme
# ---------------------------------------------------------------------------


class TestStorageScheme:
    """preflight() check 2: dvc_path URI scheme must be registered in STORAGE."""

    def test_unregistered_scheme_raises(self) -> None:
        """dvc_path with unregistered scheme raises PreflightError."""

        @TRAINERS.register_module(name="fake_trainer")
        class FakeTrainer:
            """Fake trainer for testing."""

        try:
            recipe = _make_recipe(
                component_registry="trainers",
                component_type="fake_trainer",
                inputs={
                    "checkpoint": {
                        "ref_type": "dvc_path",
                        "ref_value": "oss://mybucket/models/checkpoint.pt",
                    }
                },
            )
            with pytest.raises(PreflightError, match=r"storage scheme 'oss' not registered"):
                preflight(recipe)
        finally:
            TRAINERS._module_dict.pop("fake_trainer", None)

    def test_registered_local_scheme_passes(self) -> None:
        """dvc_path with 'local' scheme (registered) does not raise."""

        @TRAINERS.register_module(name="fake_trainer")
        class FakeTrainer:
            """Fake trainer for testing."""

        try:
            recipe = _make_recipe(
                component_registry="trainers",
                component_type="fake_trainer",
                inputs={
                    "checkpoint": {
                        "ref_type": "dvc_path",
                        "ref_value": "local:///data/models/checkpoint.pt",
                    }
                },
            )
            result = preflight(recipe)
            assert result is None
        finally:
            TRAINERS._module_dict.pop("fake_trainer", None)

    def test_bare_path_treated_as_local(self) -> None:
        """dvc_path with no URI scheme defaults to 'local' and passes when local is registered."""

        @TRAINERS.register_module(name="fake_trainer")
        class FakeTrainer:
            """Fake trainer for testing."""

        try:
            recipe = _make_recipe(
                component_registry="trainers",
                component_type="fake_trainer",
                inputs={
                    "checkpoint": {
                        "ref_type": "dvc_path",
                        "ref_value": "/data/models/checkpoint.pt",
                    }
                },
            )
            result = preflight(recipe)
            assert result is None
        finally:
            TRAINERS._module_dict.pop("fake_trainer", None)


# ---------------------------------------------------------------------------
# Check 3 — upstream existence
# ---------------------------------------------------------------------------


class TestUpstreamExistence:
    """preflight() check 3: recipe_stage_output must reference an existing stage."""

    def test_missing_upstream_stage_raises(self) -> None:
        """recipe_stage_output pointing to a non-existent stage raises PreflightError."""

        @TRAINERS.register_module(name="fake_trainer")
        class FakeTrainer:
            """Fake trainer for testing."""

        try:
            recipe = _make_recipe(
                component_registry="trainers",
                component_type="fake_trainer",
                inputs={
                    "weights": {
                        "ref_type": "recipe_stage_output",
                        "ref_value": "nonexistent_stage",
                    }
                },
            )
            with pytest.raises(
                PreflightError, match=r"unknown upstream stage 'nonexistent_stage'"
            ):
                preflight(recipe)
        finally:
            TRAINERS._module_dict.pop("fake_trainer", None)

    def test_existing_upstream_stage_passes(self) -> None:
        """recipe_stage_output pointing to a real stage does not raise."""

        @TRAINERS.register_module(name="fake_trainer")
        class FakeTrainer:
            """Fake trainer for testing."""

        @EVALUATORS.register_module(name="fake_evaluator")
        class FakeEvaluator:
            """Fake evaluator for testing."""

        try:
            recipe = ExperimentRecipe.model_validate(
                {
                    **_BASE,
                    "stages": [
                        {
                            "name": "train",
                            "component_registry": "trainers",
                            "component_type": "fake_trainer",
                            "inputs": {},
                            "config_path": "configs/train.yaml",
                            "depends_on": [],
                        },
                        {
                            "name": "eval",
                            "component_registry": "evaluators",
                            "component_type": "fake_evaluator",
                            "inputs": {
                                "weights": {
                                    "ref_type": "recipe_stage_output",
                                    "ref_value": "train",
                                }
                            },
                            "config_path": "configs/eval.yaml",
                            "depends_on": ["train"],
                        },
                    ],
                }
            )
            result = preflight(recipe)
            assert result is None
        finally:
            TRAINERS._module_dict.pop("fake_trainer", None)
            EVALUATORS._module_dict.pop("fake_evaluator", None)


# ---------------------------------------------------------------------------
# Check 1c — datasets and ota registry coverage (finding #10)
# ---------------------------------------------------------------------------


class TestDatasetAndOtaRegistryCoverage:
    """preflight() check 1: component_type must be validated for 'datasets' and 'ota'.

    _REGISTRY_BY_NAME previously only contained trainers/evaluators/converters.
    Recipes with component_registry='datasets' or 'ota' silently skipped the
    plugin-existence check, crashing with a confusing LookupError mid-DAG-run.
    """

    def test_unregistered_dataset_plugin_raises(self) -> None:
        """Unregistered component_type in 'datasets' raises PreflightError."""
        recipe = _make_recipe(
            component_registry="datasets",
            component_type="__not_registered_dataset__",
        )
        with pytest.raises(
            PreflightError, match=r"plugin '__not_registered_dataset__' not registered"
        ):
            preflight(recipe)

    def test_unregistered_ota_plugin_raises(self) -> None:
        """Unregistered component_type in 'ota' raises PreflightError."""
        recipe = _make_recipe(
            component_registry="ota",
            component_type="__not_registered_ota__",
        )
        with pytest.raises(PreflightError, match=r"plugin '__not_registered_ota__' not registered"):
            preflight(recipe)

    def test_registered_dataset_plugin_passes(self) -> None:
        """A registered dataset component_type does NOT raise."""

        @DATASETS.register_module(name="fake_dataset")
        class FakeDataset:
            """Fake dataset for testing."""

        try:
            recipe = _make_recipe(
                component_registry="datasets",
                component_type="fake_dataset",
            )
            assert preflight(recipe) is None
        finally:
            DATASETS._module_dict.pop("fake_dataset", None)

    def test_registered_ota_plugin_passes(self) -> None:
        """A registered OTA component_type does NOT raise."""

        @OTA.register_module(name="fake_ota")
        class FakeOta:
            """Fake OTA handler for testing."""

        try:
            recipe = _make_recipe(
                component_registry="ota",
                component_type="fake_ota",
            )
            assert preflight(recipe) is None
        finally:
            OTA._module_dict.pop("fake_ota", None)


# ---------------------------------------------------------------------------
# Happy path — all checks pass end-to-end
# ---------------------------------------------------------------------------


class TestHappyPath:
    """preflight() returns None when the recipe passes all checks."""

    def test_fully_valid_recipe_returns_none(self) -> None:
        """A fully valid recipe returns None without raising."""

        @TRAINERS.register_module(name="fake_trainer")
        class FakeTrainer:
            """Fake trainer for testing."""

        try:
            recipe = _make_recipe(
                component_registry="trainers",
                component_type="fake_trainer",
                inputs={
                    "data": {
                        "ref_type": "dvc_path",
                        "ref_value": "local:///data/train.jsonl",
                    }
                },
            )
            assert preflight(recipe) is None
        finally:
            TRAINERS._module_dict.pop("fake_trainer", None)
