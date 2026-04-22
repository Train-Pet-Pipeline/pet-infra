"""HTTP(S)-backed storage backend (read-only).

Used to fetch artifacts from CDNs (CloudFront, nginx, GitHub Releases…)
that expose static assets over ``http://`` or ``https://`` GET. Writes are
unsupported because most artifact CDNs do not accept PUT — uploads must
go through :class:`pet_infra.storage.s3.S3Storage`.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any, ClassVar
from urllib.parse import urlparse

import requests

from pet_infra.base import BaseStorage
from pet_infra.registry import STORAGE


@STORAGE.register_module(name="http")
class HttpStorage(BaseStorage):
    """Read-only HTTP(S) storage backend.

    Handles URIs of the form ``http://host/path`` or ``https://host/path``.
    The registry key is ``http`` (mmengine Registry keys cannot contain
    ``:``); the same backend transparently serves both schemes.
    """

    scheme: ClassVar[str] = "http"

    def __init__(
        self,
        timeout_s: float = 30.0,
        auth_token: str | None = None,
        basic_auth: tuple[str, str] | None = None,
        **_: Any,
    ) -> None:
        """Configure the HTTP client.

        Args:
            timeout_s: Per-request timeout (seconds) applied to GET and HEAD.
            auth_token: Optional bearer token; sent as
                ``Authorization: Bearer <token>``.
            basic_auth: Optional ``(username, password)`` tuple for HTTP Basic
                authentication, forwarded to ``requests`` as ``auth=...``.
            **_: Extra kwargs are accepted and ignored to keep the constructor
                forgiving when instantiated via Hydra/registry configs.
        """
        self._timeout = timeout_s
        self._headers: dict[str, str] = {}
        self._auth = basic_auth
        if auth_token:
            self._headers["Authorization"] = f"Bearer {auth_token}"

    def _check(self, uri: str) -> None:
        """Validate that ``uri`` uses an http or https scheme.

        Args:
            uri: The URI to validate.

        Raises:
            ValueError: If the URI scheme is not ``http`` or ``https``.
        """
        scheme = urlparse(uri).scheme
        if scheme not in {"http", "https"}:
            raise ValueError(
                f"HttpStorage only handles http/https URIs, got scheme={scheme!r}"
            )

    def read(self, uri: str) -> bytes:
        """Fetch and return raw bytes from the given HTTP(S) URI.

        Args:
            uri: An ``http://`` or ``https://`` URI pointing to the resource.

        Returns:
            Raw bytes of the response body.

        Raises:
            ValueError: If the URI scheme is not http/https.
            requests.HTTPError: If the response status is not 2xx.
        """
        self._check(uri)
        r = requests.get(
            uri,
            timeout=self._timeout,
            headers=self._headers,
            auth=self._auth,
        )
        r.raise_for_status()
        return r.content

    def write(self, uri: str, data: bytes) -> str:
        """Reject writes — HttpStorage is read-only by design.

        Args:
            uri: Ignored.
            data: Ignored.

        Returns:
            Never returns; always raises.

        Raises:
            NotImplementedError: Always. Use :class:`S3Storage` for uploads.
        """
        raise NotImplementedError(
            "HttpStorage is read-only; use S3Storage for uploads."
        )

    def exists(self, uri: str) -> bool:
        """Check whether the given HTTP(S) URI returns 200 to a HEAD request.

        Args:
            uri: An ``http://`` or ``https://`` URI to probe.

        Returns:
            True if a HEAD request returns status 200, False otherwise
            (including 404, 403, and other non-200 statuses).

        Raises:
            ValueError: If the URI scheme is not http/https.
        """
        self._check(uri)
        r = requests.head(
            uri,
            timeout=self._timeout,
            headers=self._headers,
            auth=self._auth,
            allow_redirects=True,
        )
        return r.status_code == 200

    def iter_prefix(self, prefix: str) -> Iterator[str]:
        """Reject prefix iteration — HTTP has no standard listing protocol.

        Args:
            prefix: Ignored.

        Yields:
            Never yields; always raises.

        Raises:
            NotImplementedError: Always. Use :class:`S3Storage` for prefix
                iteration over object stores.
        """
        raise NotImplementedError(
            "HttpStorage cannot list; use S3Storage for prefix iteration."
        )
