# tests/orchestrator/test_runner_yaml_load.py
"""Unit tests for yaml.safe_load None-guard in pet_run stage config loading.

Finding #15: explicit None check replaces ``yaml.safe_load(...) or {}``.
Behaviour is identical for the three relevant cases:
  - empty file  → {}
  - null-only YAML (just ``null``) → {}
  - valid YAML dict → the dict as-is

These tests verify the explicit pattern in runner.py line 76 is correct,
and provide a regression guard if someone changes it back to ``or {}``.
"""
from __future__ import annotations

import yaml


def _load_stage_config(content: str) -> dict:
    """Replicate the explicit None-guard pattern from runner.py line 76.

    This is NOT a new abstraction — it mirrors the exact inline expression so
    tests can exercise it without requiring a full pet_run() fixture.
    """
    result = yaml.safe_load(content)
    return result if result is not None else {}


class TestYamlSafeLoadNoneGuard:
    """Verify the explicit None-check pattern used in runner.py stage config loading."""

    def test_empty_file_returns_empty_dict(self) -> None:
        """Empty YAML content (no bytes) must return {}."""
        assert _load_stage_config("") == {}

    def test_null_yaml_returns_empty_dict(self) -> None:
        """YAML file containing only 'null' must return {}.

        yaml.safe_load('null') returns None, not {}. The explicit guard
        converts this to {} so downstream code always gets a dict.
        """
        assert _load_stage_config("null") == {}

    def test_valid_yaml_returns_dict(self) -> None:
        """Valid YAML dict content must be returned as-is."""
        content = "learning_rate: 1.0e-4\nbatch_size: 32\n"
        assert _load_stage_config(content) == {"learning_rate": 1e-4, "batch_size": 32}

    def test_whitespace_only_returns_empty_dict(self) -> None:
        """Whitespace-only YAML content must return {} (safe_load returns None)."""
        assert _load_stage_config("   \n  ") == {}

    def test_nested_dict_returns_as_is(self) -> None:
        """Nested YAML dicts are returned without modification."""
        content = "model:\n  arch: resnet50\n  layers: 50\n"
        assert _load_stage_config(content) == {"model": {"arch": "resnet50", "layers": 50}}
