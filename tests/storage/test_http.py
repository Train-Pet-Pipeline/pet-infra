"""Tests for HttpStorage backend (read-only, http.server fixture)."""
from __future__ import annotations

import http.server
import socketserver
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

# Import triggers registration side-effect
import pet_infra.storage.http as _http_storage_mod  # noqa: F401
from pet_infra.storage.http import HttpStorage


@pytest.fixture
def http_server(tmp_path: Path) -> Iterator[dict[str, object]]:
    """Spin up a stdlib http.server bound to a random port serving tmp files.

    Yields:
        A dict with keys:
            - ``base_url``: e.g. ``http://127.0.0.1:54321``.
            - ``serve_dir``: the :class:`pathlib.Path` whose contents are served.
    """
    serve_dir = tmp_path / "www"
    serve_dir.mkdir()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a: object, **kw: object) -> None:
            super().__init__(*a, directory=str(serve_dir), **kw)  # type: ignore[arg-type]

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            """Silence test-time access logs."""
            return

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield {"base_url": f"http://127.0.0.1:{port}", "serve_dir": serve_dir}
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_scheme(http_server: dict[str, object]) -> None:
    """HttpStorage advertises ``http`` as its scheme ClassVar."""
    assert HttpStorage.scheme == "http"


def test_http_read_existing(http_server: dict[str, object]) -> None:
    """read() GETs an existing file from the served directory and returns its bytes."""
    serve_dir = http_server["serve_dir"]
    assert isinstance(serve_dir, Path)
    payload = b"hello-from-cdn"
    (serve_dir / "file.bin").write_bytes(payload)

    storage = HttpStorage()
    uri = f"{http_server['base_url']}/file.bin"
    assert storage.read(uri) == payload


def test_http_exists_404(http_server: dict[str, object]) -> None:
    """exists() returns False (not raises) for a 404 path."""
    storage = HttpStorage()
    uri = f"{http_server['base_url']}/never-existed.bin"
    assert storage.exists(uri) is False


def test_http_write_raises_readonly(http_server: dict[str, object]) -> None:
    """write() raises NotImplementedError because HttpStorage is read-only."""
    storage = HttpStorage()
    uri = f"{http_server['base_url']}/whatever.bin"
    with pytest.raises(NotImplementedError, match="read-only"):
        storage.write(uri, b"payload")
