"""Tests for Hydra ConfigStore structured-config registration."""
from __future__ import annotations

import pytest
from hydra.core.config_store import ConfigStore


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
