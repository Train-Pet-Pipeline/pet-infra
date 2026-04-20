"""Tests for precompute_card_id helper."""
from __future__ import annotations

import pytest

from pet_infra.recipe.card_id import precompute_card_id


def test_basic_format() -> None:
    """First 8 chars of sha are appended after recipe_id and stage_name."""
    result = precompute_card_id(
        recipe_id="r1",
        stage_name="train",
        config_sha="abcdef1234abcdef",
    )
    assert result == "r1_train_abcdef12"


def test_deterministic() -> None:
    """Same inputs always produce the same id."""
    a = precompute_card_id("r1", "train", "abcdef1234abcdef")
    b = precompute_card_id("r1", "train", "abcdef1234abcdef")
    assert a == b


def test_different_sha_different_id() -> None:
    """Different sha values produce different ids."""
    a = precompute_card_id("r1", "train", "abcdef1234abcdef")
    b = precompute_card_id("r1", "train", "11111111aaaaaaaa")
    assert a != b


@pytest.mark.parametrize(
    "recipe_id,stage_name,config_sha",
    [
        ("", "train", "abcdef1234abcdef"),
        ("r1", "", "abcdef1234abcdef"),
        ("r1", "train", ""),
    ],
)
def test_empty_input_raises(recipe_id: str, stage_name: str, config_sha: str) -> None:
    """Empty string for any argument raises ValueError."""
    with pytest.raises(ValueError):
        precompute_card_id(recipe_id, stage_name, config_sha)
