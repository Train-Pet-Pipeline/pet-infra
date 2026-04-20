from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator


class BaseStorage(ABC):
    """Base class for all storage backends (local, S3, OSS, etc.)."""

    @abstractmethod
    def read(self, uri: str) -> bytes:
        """Read and return raw bytes from the given URI.

        Args:
            uri: The resource URI to read from.

        Returns:
            Raw bytes content.
        """
        ...

    @abstractmethod
    def write(self, uri: str, data: bytes) -> str:
        """Write data to the given URI and return the canonical URI.

        Args:
            uri: The target URI to write to.
            data: Raw bytes to write.

        Returns:
            The canonical URI where the data was written.
        """
        ...

    @abstractmethod
    def exists(self, uri: str) -> bool:
        """Check whether the given URI exists.

        Args:
            uri: The URI to check.

        Returns:
            True if the resource exists.
        """
        ...

    @abstractmethod
    def iter_prefix(self, prefix: str) -> Iterator[str]:
        """Iterate over all URIs sharing the given prefix.

        Args:
            prefix: The URI prefix to list.

        Yields:
            URIs that start with the given prefix.
        """
        ...
