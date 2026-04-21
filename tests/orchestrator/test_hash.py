# tests/orchestrator/test_hash.py
from types import SimpleNamespace
from pet_infra.orchestrator.hash import hash_stage_config


def test_canonical_json_key_order_insensitive():
    a = SimpleNamespace(config={"lr": 1e-4, "batch": 4})
    b = SimpleNamespace(config={"batch": 4, "lr": 1e-4})
    assert hash_stage_config(a, None) == hash_stage_config(b, None)


def test_override_changes_hash():
    a = SimpleNamespace(config={"lr": 1e-4})
    b = SimpleNamespace(config={"lr": 3e-4})
    assert hash_stage_config(a, None) != hash_stage_config(b, None)


def test_prev_card_uri_in_hash():
    stage = SimpleNamespace(config={"lr": 1e-4})
    c1 = SimpleNamespace(checkpoint_uri="file:///a")
    c2 = SimpleNamespace(checkpoint_uri="file:///b")
    assert hash_stage_config(stage, c1) != hash_stage_config(stage, c2)
