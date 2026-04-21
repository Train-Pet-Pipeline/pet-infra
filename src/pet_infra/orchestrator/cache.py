# src/pet_infra/orchestrator/cache.py
"""StageCache: filesystem JSON cache with corrupt-as-miss behavior (§5.2 rule 4)."""
from __future__ import annotations
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class StageCache:
    """Filesystem-backed key-value cache for stage ModelCards (serialized as JSON).

    Corrupt entries are treated as cache misses per §5.2 rule 4.
    """

    def __init__(self, root: Path) -> None:
        """Initialize cache rooted at ``root``, creating the directory if needed."""
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def has(self, key: str) -> bool:
        """Return True if a cache entry file exists (may still be corrupt)."""
        return self._path(key).exists()

    def load(self, key: str) -> dict | None:
        """Load a cached dict by key, returning None on corrupt or missing entry."""
        try:
            return json.loads(self._path(key).read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("cache corrupt for %s, treating as miss: %s", key, e)
            return None

    def save(self, key: str, card_dict: dict) -> None:
        """Persist a dict to the cache under ``key``."""
        self._path(key).write_text(json.dumps(card_dict, sort_keys=True))
