"""Tests for pet_infra.plugins.discover — plugin discovery with required-filter."""
from __future__ import annotations

import sys

import pytest

from pet_infra.registry import CONVERTERS, DATASETS, EVALUATORS, METRICS, OTA, STORAGE, TRAINERS

ALL_REGISTRIES = [TRAINERS, EVALUATORS, CONVERTERS, METRICS, DATASETS, STORAGE, OTA]

# Leaf modules that register themselves via @register_module on import.
# Both the submodule and the package must be evicted so re-import re-executes decorators.
# This covers all first-party pet-infra plugin modules registered by _register.register_all().
_EVICT_MODULES = [
    "pet_infra.storage.local",
    "pet_infra.storage.s3",
    "pet_infra.storage.http",
    "pet_infra.storage",
    "pet_infra.evaluators.noop",
    "pet_infra.evaluators",
]


@pytest.fixture()
def clean_registries():
    """Isolate discover tests from duplicate-registration errors.

    Strategy (snapshot-then-clear-all):
    1. Snapshot ALL 6 registry states before any eviction.
    2. Clear ALL registries completely so discover_plugins() starts from empty
       state — prevents downstream plugins (pet-train, pet-eval, etc.) installed
       in the shared pet-pipeline conda env from polluting "only pet-infra
       plugins" assertions.
    3. Evict pet-infra storage leaf modules so discover re-imports them.
    4. After the test, restore all registries to their pre-eviction snapshots.
       Evict leaf modules again so the next discover test starts clean.

    This covers all 7 registries: TRAINERS, EVALUATORS, CONVERTERS, METRICS,
    DATASETS, STORAGE, OTA. Previously only STORAGE was evicted, which caused
    test_discover_first_party_registries_contain_only_pet_infra_plugins to fail
    in any shared env with pet-train/pet-eval/pet-quantize/pet-ota installed.
    """
    # Step 1: snapshot BEFORE any mutation
    snapshots = {reg: dict(reg._module_dict) for reg in ALL_REGISTRIES}

    # Step 2: clear ALL registries so discover_plugins() starts from empty state
    for reg in ALL_REGISTRIES:
        reg._module_dict.clear()

    # Step 3: evict pet-infra leaf modules so re-import re-runs @register_module
    for mod in _EVICT_MODULES:
        sys.modules.pop(mod, None)

    yield

    # Step 4: restore all registries to pre-eviction state
    for reg, snap in snapshots.items():
        reg._module_dict.clear()
        reg._module_dict.update(snap)

    # Evict leaf modules so the next discover test can re-import cleanly.
    # Non-discover tests that use module-level imports of LocalStorage are
    # unaffected: they bound LocalStorage at collection time and STORAGE is
    # restored to include "local" by the snapshot above.
    for mod in _EVICT_MODULES:
        sys.modules.pop(mod, None)


class TestDiscoverPlugins:
    """All discover_plugins() tests share the clean_registries fixture."""

    @pytest.fixture(autouse=True)
    def _use_clean(self, clean_registries):  # noqa: PT004
        """Auto-apply clean_registries to every test in this class."""

    def test_discover_returns_seven_keys(self):
        """discover_plugins() returns a dict with exactly 7 canonical keys."""
        from pet_infra.plugins.discover import discover_plugins

        result = discover_plugins()
        assert set(result.keys()) == {
            "trainers",
            "evaluators",
            "converters",
            "metrics",
            "datasets",
            "storage",
            "ota",
        }

    def test_discover_storage_contains_local(self):
        """After loading the built-in entry point, storage must contain 'local'."""
        from pet_infra.plugins.discover import discover_plugins

        result = discover_plugins()
        assert "local" in result["storage"]

    def test_discover_first_party_registries_contain_only_pet_infra_plugins(self):
        """pet-infra itself ships only 'local' storage and 'pet_infra.noop_evaluator'.

        Other registries (trainers, converters, metrics) have no first-party
        pet-infra plugins. The datasets registry is populated by downstream
        plugin packages at entry-point discovery time (pet-data /
        pet-annotation); this test only asserts the shape pet-infra owns and
        tolerates downstream-supplied entries in ``datasets``.

        Uses required=["pet_infra"] to load only pet-infra's own entry point,
        isolating first-party shape from downstream plugins installed in the
        shared pet-pipeline conda env (pet-train, pet-eval, etc.).
        """
        from pet_infra.plugins.discover import discover_plugins

        result = discover_plugins(required=["pet_infra"])
        for key in ("trainers", "converters", "metrics"):
            assert result[key] == [], f"Expected {key} to be empty, got {result[key]}"
        assert "pet_infra.noop_evaluator" in result["evaluators"], result["evaluators"]

    def test_discover_with_required_existing(self):
        """discover_plugins(required=['pet_infra']) succeeds and returns same shape."""
        from pet_infra.plugins.discover import discover_plugins

        result = discover_plugins(required=["pet_infra"])
        assert set(result.keys()) == {
            "trainers",
            "evaluators",
            "converters",
            "metrics",
            "datasets",
            "storage",
            "ota",
        }
        assert "local" in result["storage"]

    def test_discover_with_required_missing(self):
        """discover_plugins(required=['__missing__']) raises RuntimeError listing the name."""
        from pet_infra.plugins.discover import discover_plugins

        with pytest.raises(RuntimeError, match="__missing__"):
            discover_plugins(required=["__missing__"])

    def test_discover_respects_required_filter_when_multiple_eps(self, monkeypatch):
        """discover_plugins(required=['alpha']) only invokes alpha's loader, not beta's."""
        from pet_infra.plugins import discover as discover_mod

        called: list[str] = []

        def make_loader(name: str):
            def _loader():
                called.append(name)
            return _loader

        class FakeEP:
            def __init__(self, name: str):
                self.name = name
                self._callable = make_loader(name)

            def load(self):
                return self._callable

        fake_eps = [FakeEP("alpha"), FakeEP("beta")]
        monkeypatch.setattr(
            discover_mod, "entry_points", lambda group: fake_eps
        )

        result = discover_mod.discover_plugins(required=["alpha"])
        assert called == ["alpha"]  # only alpha's loader ran
        assert set(result.keys()) == {
            "trainers", "evaluators", "converters", "metrics", "datasets", "storage", "ota",
        }
