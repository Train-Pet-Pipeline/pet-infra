"""Tests for recipe compose module (B7)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

FIXTURES = Path(__file__).parent / "fixtures" / "recipe"


def test_compose_returns_three_tuple():
    """compose_recipe returns (ExperimentRecipe, dict, 64-char sha256 hex)."""
    from pet_schema import ExperimentRecipe

    from pet_infra.recipe import compose_recipe

    recipe, resolved, config_sha = compose_recipe(FIXTURES / "minimal.yaml")

    assert isinstance(recipe, ExperimentRecipe)
    assert isinstance(resolved, dict)
    assert isinstance(config_sha, str)
    assert len(config_sha) == 64
    assert all(c in "0123456789abcdef" for c in config_sha)


def test_resolved_matches_yaml_content():
    """resolved dict round-trips back to the yaml content."""
    import yaml

    from pet_infra.recipe import compose_recipe

    _, resolved, _ = compose_recipe(FIXTURES / "minimal.yaml")
    raw = yaml.safe_load((FIXTURES / "minimal.yaml").read_text())

    assert resolved == raw


def test_override_mutates_description():
    """Passing an override changes the recipe field and the config sha."""
    from pet_infra.recipe import compose_recipe

    recipe_orig, _, sha_orig = compose_recipe(FIXTURES / "minimal.yaml")
    recipe_ov, resolved_ov, sha_ov = compose_recipe(
        FIXTURES / "minimal.yaml",
        overrides=["description=override-text"],
    )

    assert recipe_ov.description == "override-text"
    assert resolved_ov["description"] == "override-text"
    assert sha_ov != sha_orig


def test_missing_required_field_raises_validation_error(tmp_path):
    """A yaml missing a required field raises pydantic.ValidationError."""
    from pet_infra.recipe import compose_recipe

    bad = tmp_path / "bad.yaml"
    bad.write_text("recipe_id: only-id\n")

    with pytest.raises(ValidationError):
        compose_recipe(bad)


def test_identical_inputs_produce_identical_sha():
    """Two calls with the same file and no overrides produce the same sha."""
    from pet_infra.recipe import compose_recipe

    _, _, sha1 = compose_recipe(FIXTURES / "minimal.yaml")
    _, _, sha2 = compose_recipe(FIXTURES / "minimal.yaml")

    assert sha1 == sha2


def test_different_overrides_produce_different_sha():
    """Different override values produce different config_sha values."""
    from pet_infra.recipe import compose_recipe

    _, _, sha_a = compose_recipe(
        FIXTURES / "minimal.yaml", overrides=["description=variant-a"]
    )
    _, _, sha_b = compose_recipe(
        FIXTURES / "minimal.yaml", overrides=["description=variant-b"]
    )

    assert sha_a != sha_b


def test_sha256_is_deterministic_canonical():
    """config_sha equals sha256 of canonical JSON of resolved dict."""
    from pet_infra.recipe import compose_recipe

    _, resolved, config_sha = compose_recipe(FIXTURES / "minimal.yaml")
    expected = hashlib.sha256(
        json.dumps(resolved, sort_keys=True, default=str).encode()
    ).hexdigest()

    assert config_sha == expected
