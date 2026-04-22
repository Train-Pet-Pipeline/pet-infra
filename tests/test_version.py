"""Tests for pet-infra version parity between __version__ and installed metadata."""

import importlib.metadata

from pet_infra import __version__


def test_version_matches_pyproject():
    """__version__ must match installed package metadata (importlib.metadata).

    Prevents __version__ drift when pyproject.toml is bumped. Pattern mirrors
    pet-schema Phase 1 parity test.
    """
    installed = importlib.metadata.version("pet-infra")
    assert __version__ == installed, (
        f"__version__ ({__version__!r}) must match installed package metadata "
        f"({installed!r}). Update src/pet_infra/__init__.py when bumping "
        "pyproject.toml version."
    )
