# tests/orchestrator/test_cache.py
import pytest
import tempfile
import json
from pathlib import Path
from pet_infra.orchestrator.cache import StageCache


def test_save_load_roundtrip(tmp_path):
    cache = StageCache(root=tmp_path)
    assert not cache.has("k1")
    cache.save("k1", {"id": "k1", "metrics": {"loss": 0.1}})
    assert cache.has("k1")
    assert cache.load("k1")["metrics"]["loss"] == 0.1


def test_corrupt_treated_as_miss(tmp_path, caplog):
    cache = StageCache(root=tmp_path)
    (tmp_path / "k1.json").write_text("{invalid")
    assert cache.has("k1") is True  # file exists
    result = cache.load("k1")  # returns None on corrupt
    # contract: treated as miss
    assert result is None
    assert "cache corrupt" in caplog.text.lower()
