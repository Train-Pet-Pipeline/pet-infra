"""Tests for launch_multirun — cartesian-product sweep dispatcher.

Fixtures use the full ExperimentRecipe schema (required fields expanded) because
compose_recipe runs full Pydantic validation. PET_MULTIRUN_SYNC=1 forces the
in-process synchronous loop so monkeypatch on _run_single works.
"""
import json
from pathlib import Path

import pytest

from pet_infra.launcher import launch_multirun

# Full minimal YAML that satisfies ExperimentRecipe validation.
_RECIPE_YAML = """\
recipe_id: sweep_test
description: multirun sweep test fixture
scope: single_repo
schema_version: "2.1.0"
stages: []
variations: []
produces: []
default_storage: local
required_plugins: []
"""


def test_cartesian_product_2x2_yields_4_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given 2 values on each of 2 axes, launcher dispatches 4 runs."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    dispatched: list[dict] = []

    def fake_run_single(recipe_path: Path, overrides: dict, out_dir: Path) -> dict:
        dispatched.append(overrides)
        return {"card_path": out_dir / "card.json", "status": "ok", "overrides": overrides}

    monkeypatch.setattr("pet_infra.launcher._run_single", fake_run_single)

    recipe_fixture = tmp_path / "r.yaml"
    recipe_fixture.write_text(_RECIPE_YAML)
    results = launch_multirun(
        recipe_fixture,
        sweep_params={"trainer": ["a", "b"], "device": ["cpu", "mps"]},
        results_root=tmp_path / "out",
    )
    assert len(results) == 4
    axis_pairs = {(r["overrides"]["trainer"], r["overrides"]["device"]) for r in results}
    assert axis_pairs == {("a", "cpu"), ("a", "mps"), ("b", "cpu"), ("b", "mps")}


def test_failed_axis_does_not_block_siblings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing axis combo produces status='failed'; siblings still complete."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")

    def fake_run_single(recipe_path: Path, overrides: dict, out_dir: Path) -> dict:
        if overrides.get("trainer") == "broken":
            raise RuntimeError("boom")
        return {"card_path": out_dir / "card.json", "status": "ok", "overrides": overrides}

    monkeypatch.setattr("pet_infra.launcher._run_single", fake_run_single)
    recipe_fixture = tmp_path / "r.yaml"
    recipe_fixture.write_text(_RECIPE_YAML)
    results = launch_multirun(
        recipe_fixture,
        sweep_params={"trainer": ["good", "broken"]},
        results_root=tmp_path / "out",
    )
    statuses = {r["overrides"]["trainer"]: r["status"] for r in results}
    assert statuses["good"] == "ok"
    assert statuses["broken"] == "failed"


def test_sweep_summary_json_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """sweep_summary.json is written under results_root/<recipe_id>/."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")

    def fake_run_single(recipe_path: Path, overrides: dict, out_dir: Path) -> dict:
        return {"card_path": out_dir / "card.json", "status": "ok", "overrides": overrides}

    monkeypatch.setattr("pet_infra.launcher._run_single", fake_run_single)
    recipe_fixture = tmp_path / "r.yaml"
    recipe_fixture.write_text(_RECIPE_YAML)
    out_root = tmp_path / "out"
    launch_multirun(
        recipe_fixture,
        sweep_params={"trainer": ["a"]},
        results_root=out_root,
    )
    summary = json.loads((out_root / "sweep_test" / "sweep_summary.json").read_text())
    assert summary["recipe_id"] == "sweep_test"
    assert len(summary["runs"]) == 1


def test_single_axis_single_value_one_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Single axis with one value dispatches exactly one run."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")

    def fake_run_single(recipe_path: Path, overrides: dict, out_dir: Path) -> dict:
        return {"card_path": out_dir / "card.json", "status": "ok", "overrides": overrides}

    monkeypatch.setattr("pet_infra.launcher._run_single", fake_run_single)
    recipe_fixture = tmp_path / "r.yaml"
    recipe_fixture.write_text(_RECIPE_YAML)
    results = launch_multirun(
        recipe_fixture,
        sweep_params={"trainer": ["a"]},
        results_root=tmp_path / "out",
    )
    assert len(results) == 1


def test_overrides_propagate_to_compose_recipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that sweep_params overrides actually reach pet_run as Hydra-style strings."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    captured: list[list[str]] = []

    def fake_pet_run(
        recipe_path,
        resume=True,
        cache_root=None,
        overrides=(),
    ):
        captured.append(list(overrides))
        from datetime import datetime

        from pet_schema.model_card import ModelCard

        return ModelCard(
            id="test-id",
            version="0.1.0",
            modality="vision",
            task="classification",
            arch="test-arch",
            training_recipe="test-recipe",
            hydra_config_sha="a" * 64,
            git_shas={},
            dataset_versions={},
            checkpoint_uri="/tmp/x",
            metrics={},
            gate_status="pending",
            trained_at=datetime(2026, 1, 1),
            trained_by="operator:test",
        )

    # The lazy import inside _run_single re-resolves the attribute from the
    # module object, so patching the module attribute is sufficient.
    monkeypatch.setattr("pet_infra.orchestrator.runner.pet_run", fake_pet_run)

    recipe_fixture = tmp_path / "r.yaml"
    recipe_fixture.write_text(_RECIPE_YAML)
    launch_multirun(
        recipe_fixture,
        sweep_params={"trainer": ["a", "b"]},
        results_root=tmp_path / "out",
    )
    assert len(captured) == 2, f"Expected 2 calls to pet_run, got {len(captured)}: {captured}"
    override_sets = {frozenset(ov) for ov in captured}
    assert override_sets == {frozenset(["trainer=a"]), frozenset(["trainer=b"])}
