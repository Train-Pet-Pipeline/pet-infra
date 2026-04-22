"""Backward-compatibility tests: recipes without defaults: must still work."""
from __future__ import annotations

from pathlib import Path

from pet_infra.compose import compose_recipe

FIXTURES = Path(__file__).parent / "fixtures" / "compose"


def test_recipe_without_defaults_still_works():
    """Legacy flat recipe (no defaults key) composes without error."""
    recipe, _, _ = compose_recipe(FIXTURES / "legacy_no_defaults.yaml")
    assert recipe.recipe_id == "legacy"
    assert recipe.owner_repo == "legacy-owner"


def test_phase_3a_standalone_smoke_recipes_parse():
    """Today's smoke_tiny.yaml (no defaults: key) must still compose."""
    recipe_path = Path(__file__).parent.parent / "recipes" / "smoke_tiny.yaml"
    if recipe_path.exists():
        recipe, _, _ = compose_recipe(recipe_path)
        assert recipe.recipe_id == "smoke_tiny"
