"""Tests for Hydra ConfigStore structured-config registration."""
from __future__ import annotations

import pytest
from hydra.core.config_store import ConfigStore
from omegaconf import OmegaConf


@pytest.fixture
def fresh_config_store(monkeypatch: pytest.MonkeyPatch) -> ConfigStore:
    """Return a single fresh ConfigStore instance pinned for the test duration."""
    fresh = ConfigStore()
    monkeypatch.setattr(ConfigStore, "instance", staticmethod(lambda: fresh))
    return fresh


def test_structured_configs_registered(fresh_config_store: ConfigStore) -> None:
    from pet_infra.hydra_plugins.structured import register

    register()
    cs = ConfigStore.instance()
    assert "recipe" in cs.repo
    assert "trainer" in cs.repo
    assert "dataset" in cs.repo
    assert "evaluator" in cs.repo
    assert "converter" in cs.repo
    assert cs is fresh_config_store  # sanity: same instance throughout
    # Each node must carry _target_ for hydra.utils.instantiate support
    for group in ("recipe", "trainer", "evaluator", "converter", "dataset"):
        entry = cs.repo[group]["base.yaml"]
        assert hasattr(entry.node, "_target_"), f"group {group} has no _target_"


def test_recipe_config_has_pydantic_fields(fresh_config_store: ConfigStore) -> None:
    """hydra-zen must expose pet-schema fields, not empty slots."""
    from pet_infra.hydra_plugins.structured import register

    register()
    cs = ConfigStore.instance()
    entry = cs.repo["recipe"]["base.yaml"]
    node = entry.node
    # Use OmegaConf.to_container so ??? (MISSING) fields are included as keys
    container = OmegaConf.to_container(node, resolve=False, throw_on_missing=False)
    assert isinstance(container, dict)
    # Spot-check: ExperimentRecipe has these required fields
    assert "recipe_id" in container
    assert "description" in container
    assert "stages" in container
