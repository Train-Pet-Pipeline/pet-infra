"""Tier-2 deterministic replay: load ModelCard by ID and re-run its recipe.

Phase 4 P1-E (spec §1.4):
  - sha256 fail-fast: resolved_config_uri content hash must match card.hydra_config_sha.
  - git_shas drift warn-only: HEAD drift is a warning, not an error.

Environment variables:
    PET_CARD_REGISTRY   Directory containing <card_id>.json files.
                        Default: ``./model_cards``.
"""
from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path

from pet_schema.model_card import ModelCard

from pet_infra._register import register_all
from pet_infra.registry import STORAGE

log = logging.getLogger(__name__)

_DEFAULT_REGISTRY = "./model_cards"


def _registry_dir() -> Path:
    """Return the card registry directory from env or default.

    Returns:
        Path to the directory containing ``<card_id>.json`` files.
    """
    return Path(os.environ.get("PET_CARD_REGISTRY", _DEFAULT_REGISTRY))


def load_card(card_id: str) -> ModelCard:
    """Load a ModelCard by ID from the card registry directory.

    Looks for ``<card_id>.json`` in the directory specified by
    ``PET_CARD_REGISTRY`` (default ``./model_cards``).

    Args:
        card_id: The card identifier (must match the filename stem).

    Returns:
        The deserialized :class:`~pet_schema.model_card.ModelCard`.

    Raises:
        FileNotFoundError: If no JSON file with the given ID is found.
    """
    registry = _registry_dir()
    card_path = registry / f"{card_id}.json"
    if not card_path.exists():
        raise FileNotFoundError(
            f"Card '{card_id}' not found in registry at {registry}. "
            f"Expected file: {card_path}"
        )
    return ModelCard.model_validate_json(card_path.read_text())


def _current_git_shas() -> dict[str, str]:
    """Return a mapping of repo-name → HEAD SHA for sibling repos.

    Walks up from this file's directory to find the Train-Pet-Pipeline root
    (expected parent at grandparent of ``src/pet_infra/``). If the root cannot
    be located (CI context, installed package), returns ``{}`` so drift
    detection no-ops rather than crashing.

    Returns:
        Dict mapping repo directory names to their current HEAD SHA,
        or ``{}`` if the repo root cannot be found.
    """
    try:
        # Structure: <root>/pet-infra/src/pet_infra/replay.py
        # parents: [0]=replay.py, [1]=pet_infra, [2]=src, [3]=pet-infra, [4]=root
        module_file = Path(__file__).resolve()
        root = module_file.parents[4]
        # Sanity-check: root must contain at least one sibling repo
        siblings = [
            p for p in root.iterdir()
            if p.is_dir() and (p / ".git").exists() and p.name != "pet-infra"
        ]
        if not siblings:
            log.debug("_current_git_shas: no sibling repos found at %s; skipping drift check", root)
            return {}
        result: dict[str, str] = {}
        for sibling in siblings:
            try:
                sha = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(sibling),
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
                result[sibling.name] = sha
            except (subprocess.CalledProcessError, OSError):
                # Non-fatal: skip repos where git fails (submodules, etc.)
                pass
        return result
    except Exception:  # noqa: BLE001
        log.debug("_current_git_shas: failed to walk sibling repos; returning {}")
        return {}


def verify_and_load_config(card: ModelCard) -> str:
    """Verify sha256 of the card's resolved config and return its YAML text.

    Reads ``card.resolved_config_uri`` via the STORAGE registry, computes its
    sha256, and compares it to ``card.hydra_config_sha``.

    Args:
        card: The :class:`~pet_schema.model_card.ModelCard` to verify.

    Returns:
        The raw YAML text of the resolved config.

    Raises:
        ValueError: If ``card.resolved_config_uri`` is ``None``.
        ValueError: If the sha256 of the resolved config does not match
            ``card.hydra_config_sha``.
    """
    if card.resolved_config_uri is None:
        raise ValueError(
            f"Card '{card.id}' has no resolved_config_uri. "
            "This card was created before P1-C and cannot be deterministically replayed. "
            "Re-run via 'pet run <recipe_path>' to generate a replayable card."
        )

    register_all()
    # Determine storage backend from URI scheme
    from urllib.parse import urlparse  # noqa: PLC0415

    scheme = urlparse(card.resolved_config_uri).scheme
    storage = STORAGE.build({"type": scheme})
    raw_bytes = storage.read(card.resolved_config_uri)

    actual_sha = hashlib.sha256(raw_bytes).hexdigest()
    if actual_sha != card.hydra_config_sha:
        raise ValueError(
            f"sha256 mismatch for resolved_config_uri of card '{card.id}': "
            f"expected hydra_config_sha={card.hydra_config_sha!r}, "
            f"got sha256={actual_sha!r}. "
            "The config file may have been modified after training. "
            "Re-run via 'pet run <recipe_path>' to generate a fresh replayable card."
        )

    return raw_bytes.decode("utf-8")


def check_git_drift(card: ModelCard) -> list[str]:
    """Compare card.git_shas against current HEAD SHAs; return drift warnings.

    Drift is warn-only per spec §1.4 — the caller decides whether to print
    warnings; this function never raises.

    Args:
        card: The :class:`~pet_schema.model_card.ModelCard` to check.

    Returns:
        List of human-readable warning strings (empty if no drift or if
        ``_current_git_shas`` returns ``{}``).
    """
    current = _current_git_shas()
    if not current:
        return []

    warnings: list[str] = []
    for repo, card_sha in card.git_shas.items():
        current_sha = current.get(repo)
        if current_sha is None:
            continue  # Repo not found locally — skip silently
        if current_sha != card_sha:
            warnings.append(
                f"[drift] {repo}: card sha={card_sha[:12]!r}, "
                f"current HEAD={current_sha[:12]!r} — "
                "results may differ from original run"
            )
    return warnings


def replay(
    card_id: str,
    dry_run: bool = False,
) -> ModelCard | None:
    """Replay a training run from a ModelCard's resolved config.

    Steps (spec §1.4):
    1. Load card from registry.
    2. Verify sha256 of resolved_config_uri vs card.hydra_config_sha (fail-fast).
    3. Check git_shas drift (warn-only).
    4. If ``dry_run``: print resolved config to stdout and return ``None``.
    5. Otherwise: write resolved config to a tempfile and call ``pet_run``.

    Args:
        card_id: The card identifier to replay.
        dry_run: If ``True``, print the resolved config YAML and exit without
            invoking the launcher.

    Returns:
        The resulting :class:`~pet_schema.model_card.ModelCard` from
        ``pet_run``, or ``None`` when ``dry_run=True``.

    Raises:
        FileNotFoundError: If the card is not found in the registry.
        ValueError: If ``resolved_config_uri`` is missing or sha256 mismatches.
    """
    import click  # noqa: PLC0415

    card = load_card(card_id)
    config_yaml = verify_and_load_config(card)

    drift_warnings = check_git_drift(card)
    for warning in drift_warnings:
        click.secho(f"WARNING: {warning}", fg="yellow", err=True)

    if dry_run:
        click.echo(f"# replay --dry-run: card_id={card_id}")
        click.echo(config_yaml)
        return None

    # Write resolved config to tempfile and run via pet_run
    from pet_infra.orchestrator.runner import pet_run  # noqa: PLC0415

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, prefix=f"replay_{card_id}_"
    ) as f:
        f.write(config_yaml)
        tmp_path = Path(f.name)

    try:
        result_card = pet_run(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return result_card
