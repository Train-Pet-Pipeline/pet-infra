"""Filesystem-backed storage backend."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse

from pet_infra.base import BaseStorage
from pet_infra.registry import STORAGE


@STORAGE.register_module(name="local")
class LocalStorage(BaseStorage):
    """Local filesystem storage backend.

    Handles URIs of the form ``local:///absolute/path/to/file``.
    """

    scheme: ClassVar[str] = "local"

    def _path(self, uri: str) -> Path:
        """Parse a local:// URI and return its Path.

        Args:
            uri: A URI with ``local://`` scheme.

        Returns:
            The corresponding :class:`pathlib.Path`.

        Raises:
            ValueError: If the URI scheme is not ``local``.
        """
        parsed = urlparse(uri)
        if parsed.scheme != self.scheme:
            raise ValueError(f"LocalStorage cannot handle scheme={parsed.scheme!r}")
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
