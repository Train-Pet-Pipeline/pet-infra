"""Integration: the Phase 2 smoke recipe preflights cleanly when pet-data
and pet-annotation plugin packages are installed into the environment.

Pre-requisite: the test env must have pet-data >= 1.2.0 and
pet-annotation >= 2.0.0 installed (editable or from tag). The pet-infra
CI workflow ``plugin-discovery.yml`` pins them to ``v1.2.0`` / ``v2.0.0``;
locally a developer can use the shared ``pet-pipeline`` conda env.

If either package is missing the two tests skip with a clear message so
contributors without the downstream repos installed are not blocked.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_RECIPE = REPO_ROOT / "recipes" / "pet_data_ingest_smoke.yaml"

# pet-annotation v2.0.0 uses the 4-paradigm model (llm / classifier / rule / human)
# per pet-schema v2.1.0 four-table structure.
PHASE2_DATASET_KEYS = {
    "pet_data.vision_frames",
    "pet_data.audio_clips",
    "pet_annotation.llm",
    "pet_annotation.classifier",
    "pet_annotation.rule",
    "pet_annotation.human",
}

_MISSING_DOWNSTREAM_REASON = (
    "pet-data / pet-annotation v2.0.0 not installed — install via "
    "plugin-discovery CI matrix or the pet-pipeline conda env"
)


def _downstream_installed() -> bool:
    """Return True when both Phase 2 plugin packages import."""
    return all(
        importlib.util.find_spec(name) is not None
        for name in ("pet_data", "pet_annotation")
    )


pytestmark = pytest.mark.skipif(
    not _downstream_installed(), reason=_MISSING_DOWNSTREAM_REASON
)


def test_phase2_dataset_plugins_discoverable() -> None:
    """discover_plugins() surfaces the 4 Phase 2 dataset keys."""
    from pet_infra.plugins.discover import discover_plugins
    from pet_infra.registry import DATASETS

    discovered = discover_plugins()
    assert "datasets" in discovered
    assert PHASE2_DATASET_KEYS <= set(DATASETS.module_dict.keys()), (
        f"Missing Phase 2 dataset plugin keys. "
        f"Expected ⊇ {PHASE2_DATASET_KEYS}, "
        f"got {sorted(DATASETS.module_dict.keys())}"
    )


def test_phase2_smoke_recipe_preflight_exits_zero() -> None:
    """`pet validate --recipe recipes/pet_data_ingest_smoke.yaml` exits 0."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pet_infra.cli",
            "validate",
            "--recipe",
            str(SMOKE_RECIPE),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"smoke recipe preflight failed.\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "preflight: OK" in result.stdout
