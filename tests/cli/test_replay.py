"""Tests for `pet run --replay <card-id>` CLI (P1-E, spec §1.4).

Acceptance criteria:
  - sha256 fail-fast: resolved_config_uri content hash must match card.hydra_config_sha.
  - git_shas drift warn-only: HEAD drift is a warning, not an error.
  - --dry-run: prints resolved_config YAML and exits 0 without running launcher.
  - missing resolved_config_uri: exits non-zero with actionable message.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from pet_schema.model_card import ModelCard

# Use the same Python env as the test suite for the `pet` binary.
_PET_BIN = str(Path(sys.executable).parent / "pet")


def _make_card_kwargs(**overrides) -> dict:
    """Return minimal valid ModelCard kwargs."""
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
        resolved_config_uri=None,
    )
    base.update(overrides)
    return base


def _write_resolved_config(tmp_path: Path, content: str = "recipe_id: test\n") -> Path:
    """Write a resolved config YAML and return its path."""
    p = tmp_path / "resolved_config.yaml"
    p.write_text(content)
    return p


def _write_card(tmp_path: Path, **kwargs) -> Path:
    """Write a ModelCard JSON to tmp_path/card.json and return the path."""
    card = ModelCard(**_make_card_kwargs(**kwargs))
    p = tmp_path / "card.json"
    p.write_text(card.model_dump_json(indent=2))
    return p


class TestReplayDryRun:
    """pet run --replay <id> --dry-run: prints resolved config, exits 0."""

    def test_replay_dispatches_with_resolved_config(self, tmp_path: Path) -> None:
        """--replay <id> --dry-run prints resolved_config and card id, exits 0."""
        config_content = "recipe_id: test-recipe-001\nstages: []\n"
        cfg_path = _write_resolved_config(tmp_path, config_content)
        sha = hashlib.sha256(cfg_path.read_bytes()).hexdigest()

        card_path = _write_card(
            tmp_path,
            id="card-replay-001",
            hydra_config_sha=sha,
            resolved_config_uri=f"file://{cfg_path}",
        )

        registry_dir = tmp_path / "registry"
        registry_dir.mkdir()
        (registry_dir / "card-replay-001.json").write_text(card_path.read_text())

        r = subprocess.run(
            [
                _PET_BIN,
                "run",
                "--replay",
                "card-replay-001",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            env={
                **__import__("os").environ,
                "PET_CARD_REGISTRY": str(registry_dir),
            },
        )
        assert r.returncode == 0, f"stderr: {r.stderr}\nstdout: {r.stdout}"
        # Must print resolved config content and the card ID
        assert "recipe_id" in r.stdout or "recipe_id" in r.stderr
        assert "card-replay-001" in r.stdout or "card-replay-001" in r.stderr


class TestReplayMissingUri:
    """pet run --replay <id>: card with resolved_config_uri=None must fail."""

    def test_replay_missing_resolved_config_errors(self, tmp_path: Path) -> None:
        """Card with resolved_config_uri=None: CLI exits non-zero with 'resolved_config_uri'."""
        card_path = _write_card(
            tmp_path,
            id="card-no-uri",
            resolved_config_uri=None,
        )

        registry_dir = tmp_path / "registry"
        registry_dir.mkdir()
        (registry_dir / "card-no-uri.json").write_text(card_path.read_text())

        r = subprocess.run(
            [
                _PET_BIN,
                "run",
                "--replay",
                "card-no-uri",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            env={
                **__import__("os").environ,
                "PET_CARD_REGISTRY": str(registry_dir),
            },
        )
        assert r.returncode != 0
        combined = r.stdout + r.stderr
        assert "resolved_config_uri" in combined


class TestReplaySha256Mismatch:
    """pet run --replay <id>: sha256 mismatch must fail with actionable message."""

    def test_replay_sha256_mismatch_fails(self, tmp_path: Path) -> None:
        """Card.hydra_config_sha != sha256(read(uri)): exits non-zero."""
        config_content = "recipe_id: test-recipe-001\nstages: []\n"
        cfg_path = _write_resolved_config(tmp_path, config_content)
        # Deliberately wrong sha
        wrong_sha = "0" * 64

        card_path = _write_card(
            tmp_path,
            id="card-sha-mismatch",
            hydra_config_sha=wrong_sha,
            resolved_config_uri=f"file://{cfg_path}",
        )

        registry_dir = tmp_path / "registry"
        registry_dir.mkdir()
        (registry_dir / "card-sha-mismatch.json").write_text(card_path.read_text())

        r = subprocess.run(
            [
                _PET_BIN,
                "run",
                "--replay",
                "card-sha-mismatch",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            env={
                **__import__("os").environ,
                "PET_CARD_REGISTRY": str(registry_dir),
            },
        )
        assert r.returncode != 0
        combined = r.stdout + r.stderr
        assert "sha256" in combined.lower() or "hydra_config_sha" in combined


class TestReplayGitShaDrift:
    """pet run --replay <id>: git_shas drift is a warning, not an error."""

    def test_replay_git_shas_drift_warns_only(self, tmp_path: Path) -> None:
        """Card.git_shas differs from current HEAD: exits 0 but warns about drift."""
        config_content = "recipe_id: test-recipe-001\nstages: []\n"
        cfg_path = _write_resolved_config(tmp_path, config_content)
        sha = hashlib.sha256(cfg_path.read_bytes()).hexdigest()

        card_path = _write_card(
            tmp_path,
            id="card-drift",
            hydra_config_sha=sha,
            # git_shas differs from what _current_git_shas() would return in CI
            git_shas={"pet-train": "aaaa1111bbbb2222cccc3333dddd4444eeee5555"},
            resolved_config_uri=f"file://{cfg_path}",
        )

        registry_dir = tmp_path / "registry"
        registry_dir.mkdir()
        (registry_dir / "card-drift.json").write_text(card_path.read_text())

        r = subprocess.run(
            [
                _PET_BIN,
                "run",
                "--replay",
                "card-drift",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            env={
                **__import__("os").environ,
                "PET_CARD_REGISTRY": str(registry_dir),
            },
        )
        # Must exit 0 — drift is warn-only
        assert r.returncode == 0, f"stderr: {r.stderr}\nstdout: {r.stdout}"
        combined = r.stdout + r.stderr
        assert "drift" in combined.lower() or "warn" in combined.lower()


class TestReplayMissingArgs:
    """pet run without recipe_path and without --replay must error clearly."""

    def test_run_without_recipe_or_replay_errors(self) -> None:
        """pet run with no recipe_path and no --replay exits non-zero."""
        r = subprocess.run(
            [_PET_BIN, "run"],
            capture_output=True,
            text=True,
        )
        assert r.returncode != 0
