"""Filesystem-backed storage backend."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse

from pet_infra.base import BaseStorage
from pet_infra.registry import STORAGE

# Both names are first-class. ``local://`` is the canonical write scheme;
# ``file://`` is accepted everywhere so P1-C resolved_config_uri round-trips.
@STORAGE.register_module(name="file")
@STORAGE.register_module(name="local")
class LocalStorage(BaseStorage):
    """Local filesystem storage backend.

    Handles URIs of the form ``local:///absolute/path/to/file`` or
    ``file:///absolute/path/to/file``. Both schemes are first-class
    (see P1-C: launcher writes ``file://`` URIs; P1-E: replay reads them).

    The canonical write output always uses ``local://`` (see :meth:`write`).
    """

    scheme: ClassVar[str] = "local"
    _VALID_SCHEMES: ClassVar[frozenset[str]] = frozenset({"local", "file"})

    def _path(self, uri: str) -> Path:
        """Parse a ``local://`` or ``file://`` URI and return its :class:`~pathlib.Path`.

        Args:
            uri: A URI with ``local://`` or ``file://`` scheme.

        Returns:
            The corresponding :class:`pathlib.Path`.

        Raises:
            ValueError: If the URI scheme is not in ``{'local', 'file'}``.
        """
        parsed = urlparse(uri)
        if parsed.scheme not in self._VALID_SCHEMES:
            raise ValueError(
                f"LocalStorage cannot handle scheme={parsed.scheme!r}; "
                f"expected scheme in {{'local', 'file'}}"
            )
        return Path(parsed.path)

    def read(self, uri: str) -> bytes:
        """Read and return raw bytes from the given local URI.

        Args:
            uri: A ``local://`` URI pointing to the file to read.

        Returns:
            Raw bytes content of the file.
        """
        return self._path(uri).read_bytes()

    def write(self, uri: str, data: bytes) -> str:
        """Write data to the given local URI, creating parent dirs as needed.

        Args:
            uri: A ``local://`` URI pointing to the target file.
            data: Raw bytes to write.

        Returns:
            The canonical ``local://`` URI where data was written.
        """
        p = self._path(uri)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return f"{self.scheme}://{p}"

    def exists(self, uri: str) -> bool:
        """Check whether the given local URI exists on disk.

        Args:
            uri: A ``local://`` URI to check.

        Returns:
            True if the path exists, False otherwise.
        """
        return self._path(uri).exists()

    def iter_prefix(self, prefix: str) -> Iterator[str]:
        """Iterate over all file URIs under the given local prefix.

        Args:
            prefix: A ``local://`` URI prefix (directory path).

        Yields:
            ``local://`` URIs for every file found under the prefix, sorted.
        """
        root = self._path(prefix)
        if root.is_file():
            yield f"{self.scheme}://{root}"
            return
        for p in sorted(root.rglob("*")):
            if p.is_file():
                yield f"{self.scheme}://{p}"
