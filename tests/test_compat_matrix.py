"""Guards on docs/compatibility_matrix.yaml — Phase 2 release pinning.

The matrix is the source-of-truth for which version of each repo ships
together. If someone lands a breaking bump without updating the matrix
the test fails loudly so reviewers notice.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

MATRIX_PATH = Path(__file__).resolve().parents[1] / "docs" / "compatibility_matrix.yaml"


@pytest.fixture(scope="module")
def matrix() -> dict:
    """Parsed compatibility_matrix.yaml."""
    return yaml.safe_load(MATRIX_PATH.read_text())


def test_matrix_has_phase_2_release(matrix: dict) -> None:
    """The 2026.05 Phase 2 release exists and pins the Phase 2 versions."""
    releases = {r["release"]: r for r in matrix["releases"]}
    assert "2026.05" in releases, f"missing 2026.05 release; got {sorted(releases)}"
    r = releases["2026.05"]
    assert r["pet_data"] == "1.1.0", r
    assert r["pet_annotation"] == "1.1.0", r
    assert r["pet_infra"] == "2.1.0", r
    assert r["pet_schema"] == "2.0.0", r


def test_matrix_has_2026_06_release(matrix: dict) -> None:
    """The 2026.06 row exists with Phase 2 final version pins."""
    releases = {r["release"]: r for r in matrix["releases"]}
    assert "2026.06" in releases, f"missing 2026.06 release; got {sorted(releases)}"
    r = releases["2026.06"]
    assert r["pet_schema"] == "2.1.0", r
    assert r["pet_infra"] == "2.2.0", r
    assert r["pet_data"] == "1.2.0", r
    assert r["pet_annotation"] == "2.0.0", r
