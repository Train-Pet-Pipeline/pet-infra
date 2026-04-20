"""Helpers for computing deterministic ModelCard identifiers."""
from __future__ import annotations


def precompute_card_id(recipe_id: str, stage_name: str, config_sha: str) -> str:
    """Return a deterministic ``ModelCard.id`` of the form ``{recipe_id}_{stage_name}_{sha8}``.

    ``config_sha`` is truncated to its first 8 hex characters — sufficient for
    intra-experiment uniqueness while keeping ids human-readable.
    """
    if not (recipe_id and stage_name and config_sha):
        raise ValueError("all three inputs required to precompute card id")
    return f"{recipe_id}_{stage_name}_{config_sha[:8]}"
