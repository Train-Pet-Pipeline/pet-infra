"""P1-D: launch_multirun consumes ExperimentRecipe.variations cartesian-style.

Spec §1.3 / §3.3 / §3.5: cartesian product over recipe.variations with link_to
co-iteration (zip) and fail-fast on link_to length mismatch / unknown axis /
CLI -m conflict / hydra.sweeper.params conflict / unknown axis.stage.

PET_MULTIRUN_SYNC=1 forces the in-process synchronous loop so monkeypatch on
_run_single works. PET_FORCE_CLEARML_OFFLINE=1 short-circuits ClearML setup
in the launcher so the per-variation tag is collected without server calls.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from pet_infra.launcher import launch_multirun

_FIXT = Path(__file__).resolve().parents[1] / "fixtures" / "recipe"


def _stub_pet_run_factory():
    """Build a fake pet_run that returns a valid ModelCard without executing stages."""

    def fake_pet_run(recipe_path, resume=True, cache_root=None, overrides=()):
        from pet_schema.model_card import ModelCard

        return ModelCard(
            id="stub-id",
            version="0.1.0",
            modality="vision",
            task="classification",
            arch="stub-arch",
            training_recipe="stub-recipe",
            hydra_config_sha="b" * 64,
            git_shas={},
            dataset_versions={},
            checkpoint_uri="/tmp/x",
            metrics={},
            gate_status="pending",
            trained_at=datetime(2026, 1, 1),
            trained_by="operator:test",
        )

    return fake_pet_run


def test_variations_cartesian(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """2 axes × 2 values = 4 cartesian variations."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    monkeypatch.setattr("pet_infra.orchestrator.runner.pet_run", _stub_pet_run_factory())
    summary = launch_multirun(
        recipe_path=_FIXT / "with_variations.yaml",
        output_dir=tmp_path,
    )
    assert len(summary["variations"]) == 4


def test_variations_link_to_co_iteration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """axis B link_to=A; both have 3 values → result = 3 (zip), NOT 9 (product)."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    monkeypatch.setattr("pet_infra.orchestrator.runner.pet_run", _stub_pet_run_factory())
    summary = launch_multirun(
        recipe_path=_FIXT / "with_link_to.yaml",
        output_dir=tmp_path,
    )
    assert len(summary["variations"]) == 3


def test_clearml_tag_injected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each variation result carries clearml_tags=['variation:<axis>=<val>', ...]."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    monkeypatch.setenv("PET_FORCE_CLEARML_OFFLINE", "1")
    monkeypatch.setattr("pet_infra.orchestrator.runner.pet_run", _stub_pet_run_factory())
    summary = launch_multirun(
        recipe_path=_FIXT / "with_variations.yaml",
        output_dir=tmp_path,
    )
    for v in summary["variations"]:
        assert any(t.startswith("variation:") for t in v["clearml_tags"])


# Spec §1.3 fail-fast conditions


def test_link_to_length_mismatch_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """link_to with different value-list lengths → ValueError."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    with pytest.raises(ValueError, match="link_to.*length"):
        launch_multirun(
            recipe_path=_FIXT / "link_to_mismatch.yaml",
            output_dir=tmp_path,
        )


def test_link_to_unknown_axis_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """link_to pointing at non-existent axis → ValueError."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    with pytest.raises(ValueError, match="link_to.*unknown"):
        launch_multirun(
            recipe_path=_FIXT / "link_to_unknown.yaml",
            output_dir=tmp_path,
        )


def test_variations_with_cli_multirun_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """recipe.variations + CLI -m simultaneously → fail-fast."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    with pytest.raises(ValueError, match="variations.*-m|multirun.*conflict"):
        launch_multirun(
            recipe_path=_FIXT / "with_variations.yaml",
            overrides=["-m", "+ablation.lr=[1e-4,1e-3]"],
            output_dir=tmp_path,
        )


def test_variations_with_hydra_sweeper_params_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """recipe.variations + YAML hydra.sweeper.params simultaneously → fail-fast."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    with pytest.raises(
        ValueError, match="variations.*hydra.sweeper|sweeper.*conflict"
    ):
        launch_multirun(
            recipe_path=_FIXT / "variations_and_sweeper.yaml",
            output_dir=tmp_path,
        )


def test_variation_stage_unknown_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AblationAxis.stage must be in recipe.stages set.

    pet-schema ExperimentRecipe._cross_validate already enforces this at
    Pydantic validation time (raises ValueError via ValidationError).
    """
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    with pytest.raises(ValueError, match="stage.*not found|stage.*unknown"):
        launch_multirun(
            recipe_path=_FIXT / "axis_stage_unknown.yaml",
            output_dir=tmp_path,
        )
