"""P1-C: each variation writes resolved_config.yaml + exposes file:// URI.

Replay (P1-E) will SHA-verify the dumped YAML against ModelCard.resolved_config_uri,
so the dump MUST come from OmegaConf.to_yaml(cfg, resolve=True) for parity.

These tests force PET_MULTIRUN_SYNC=1 and monkeypatch _run_single only when the
goal is to exercise launch_multirun's aggregation. Tests that assert the actual
YAML dump go through the real _run_single + a stubbed pet_run.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from pet_infra.launcher import _run_single, launch_multirun

# Full minimal YAML satisfying ExperimentRecipe validation (mirrors
# tests/test_launcher_multirun.py's _RECIPE_YAML so compose_recipe accepts it).
_RECIPE_YAML = """\
recipe_id: resolved_cfg_test
description: P1-C resolved-config dump test fixture
scope: single_repo
schema_version: "2.1.0"
stages: []
variations: []
produces: []
default_storage: local
required_plugins: []
"""


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


def test_run_single_writes_resolved_config_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_run_single dumps the OmegaConf-resolved recipe to <out_dir>/resolved_config.yaml."""
    monkeypatch.setattr("pet_infra.orchestrator.runner.pet_run", _stub_pet_run_factory())

    recipe_fixture = tmp_path / "r.yaml"
    recipe_fixture.write_text(_RECIPE_YAML)
    out_dir = tmp_path / "combo_a"

    result = _run_single(recipe_fixture, {"trainer": "a"}, out_dir)

    cfg_file = out_dir / "resolved_config.yaml"
    assert cfg_file.exists(), "resolved_config.yaml must be written under out_dir"
    parsed = yaml.safe_load(cfg_file.read_text())
    # The override should appear in the resolved view (compose_recipe applies overrides).
    assert parsed.get("trainer") == "a"

    # URI is absolute file:// pointing at the dumped yaml.
    uri = result["resolved_config_uri"]
    assert uri.startswith("file://"), uri
    assert Path(uri.removeprefix("file://")) == cfg_file.resolve()


def test_resolved_config_uri_propagates_into_sweep_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every SweepResult and every sweep_summary.json entry carries resolved_config_uri."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")
    monkeypatch.setattr("pet_infra.orchestrator.runner.pet_run", _stub_pet_run_factory())

    recipe_fixture = tmp_path / "r.yaml"
    recipe_fixture.write_text(_RECIPE_YAML)
    out_root = tmp_path / "out"

    results = launch_multirun(
        recipe_fixture,
        sweep_params={"lr": [1e-4, 1e-3]},
        results_root=out_root,
    )

    assert len(results) == 2
    for r in results:
        assert r["status"] == "ok"
        uri = r["resolved_config_uri"]
        assert uri.startswith("file://"), uri
        cfg_path = Path(uri.removeprefix("file://"))
        assert cfg_path.exists()
        parsed = yaml.safe_load(cfg_path.read_text())
        assert parsed["lr"] == r["overrides"]["lr"]

    summary = json.loads(
        (out_root / "resolved_cfg_test" / "sweep_summary.json").read_text()
    )
    assert {run["resolved_config_uri"] for run in summary["runs"]} == {
        r["resolved_config_uri"] for r in results
    }


def test_failed_axis_omits_resolved_config_uri(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing combo records resolved_config_uri=None so summary stays parseable."""
    monkeypatch.setenv("PET_MULTIRUN_SYNC", "1")

    def fake_run_single(recipe_path: Path, overrides: dict, out_dir: Path) -> dict:
        raise RuntimeError("boom")

    monkeypatch.setattr("pet_infra.launcher._run_single", fake_run_single)

    recipe_fixture = tmp_path / "r.yaml"
    recipe_fixture.write_text(_RECIPE_YAML)
    results = launch_multirun(
        recipe_fixture,
        sweep_params={"trainer": ["broken"]},
        results_root=tmp_path / "out",
    )
    assert len(results) == 1
    assert results[0]["status"] == "failed"
    assert results[0]["resolved_config_uri"] is None
