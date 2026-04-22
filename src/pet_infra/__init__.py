"""Shared infrastructure for Train-Pet-Pipeline."""

# Peer dependency check: pet-schema is a peer-dep per DEV_GUIDE §11 (β style).
# Installer is responsible for providing a compatible pet-schema before importing pet-infra.
try:
    import pet_schema  # noqa: F401
except ImportError as e:
    raise ImportError(
        "pet-infra requires pet-schema to be installed as a peer dependency. "
        "Install via: pip install 'pet-schema @ git+https://...@<tag>' "
        "using the tag pinned in pet-infra/docs/compatibility_matrix.yaml."
    ) from e

__version__ = "2.5.0"
