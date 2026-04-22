"""Shared fixtures for pet-infra CLI replay tests."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pet_schema.model_card import ModelCard


def _make_card_kwargs(**overrides) -> dict:
    """Return a minimal dict of valid ModelCard kwargs."""
    base = dict(
        id="card-replay-001",
        version="v1",
        modality="vision",
        task="classification",
        arch="resnet",
        training_recipe="smoke_tiny",
        hydra_config_sha="abc123sha256",
        git_shas={"pet-train": "deadbeef01234567"},
        dataset_versions={"imagenet": "v1"},
        checkpoint_uri="file:///tmp/model.pt",
        metrics={"accuracy": 0.9},
        gate_status="passed",
        trained_at=datetime(2026, 4, 21, tzinfo=UTC),
        trained_by="tester",
    )
    base.update(overrides)
    return base


@pytest.fixture
def card_kwargs():
    """Return minimal valid ModelCard kwargs."""
    return _make_card_kwargs()


@pytest.fixture
def model_card(card_kwargs) -> ModelCard:
    """Return a minimal valid ModelCard."""
    return ModelCard(**card_kwargs)


@pytest.fixture
def card_json_path(tmp_path: Path, model_card: ModelCard) -> Path:
    """Write a ModelCard to a temp JSON file and return its path."""
    p = tmp_path / "card.json"
    p.write_text(model_card.model_dump_json(indent=2))
    return p


@pytest.fixture
def resolved_config_yaml(tmp_path: Path) -> Path:
    """Write a minimal resolved config YAML to a temp file and return its path."""
    import yaml

    config = {
        "recipe_id": "test-recipe-001",
        "stages": [],
        "experiment_logger": {"name": "null"},
    }
    p = tmp_path / "resolved_config.yaml"
    p.write_text(yaml.safe_dump(config, sort_keys=True))
    return p
