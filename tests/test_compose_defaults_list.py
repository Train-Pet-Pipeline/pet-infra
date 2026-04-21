"""Tests for Hydra defaults-list resolution in compose_recipe."""
from __future__ import annotations

from pathlib import Path

import pytest

from pet_infra.compose import ComposeError, compose_recipe

FIXTURES = Path(__file__).parent / "fixtures" / "compose"


def test_single_base_defaults_merged():
    """Single defaults entry merges base fields into top-level recipe."""
    recipe = compose_recipe(FIXTURES / "single_base.yaml")
    assert recipe.recipe_id == "test_single"
    assert recipe.owner_repo == "test-owner"
    assert recipe.description == "base-a description"


def test_nested_defaults_later_wins():
    """Later defaults entries override earlier; top-level overrides all defaults."""
    recipe = compose_recipe(FIXTURES / "nested.yaml")
    assert recipe.owner_repo == "overridden-owner"
    assert recipe.description == "overridden"  # top-level override wins


def test_circular_defaults_raises():
    """Circular defaults chains raise ComposeError."""
    with pytest.raises(ComposeError, match="circular"):
        compose_recipe(FIXTURES / "circular.yaml")


def test_missing_defaults_target_raises():
    """Missing defaults target raises ComposeError with 'not found'."""
    missing = FIXTURES / "missing_target.yaml"
    missing.write_text("defaults:\n  - does_not_exist\nrecipe_id: x\n")
    try:
        with pytest.raises(ComposeError, match="not found"):
            compose_recipe(missing)
    finally:
        missing.unlink()
