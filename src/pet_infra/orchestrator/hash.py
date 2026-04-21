# src/pet_infra/orchestrator/hash.py
"""Canonical-JSON sha256 hash for stage cache keys (§5.2 rule 4)."""
from __future__ import annotations
import hashlib
import json
from typing import Any


def hash_stage_config(stage: Any, prev_card: Any) -> str:
    """Compute a stable sha256 hash of a stage's config plus the previous card URI.

    Args:
        stage: Object with a ``.config`` dict attribute.
        prev_card: Previous stage's ModelCard (or SimpleNamespace with
            ``.checkpoint_uri``), or ``None`` for the first stage.

    Returns:
        Hex-encoded sha256 string.
    """
    payload = json.dumps(stage.config, sort_keys=True, separators=(",", ":"))
    payload += (prev_card.checkpoint_uri if prev_card else "")
    return hashlib.sha256(payload.encode()).hexdigest()
