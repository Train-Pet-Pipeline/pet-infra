"""Tests for LocalStorage ``file://`` scheme support (P1-E coupling fix).

The launcher (P1-C) writes ``resolved_config_uri = f"file://{cfg_path}"``
(POSIX absolute path). LocalStorage must accept both ``local://`` and ``file://``
schemes so ``STORAGE.build({"type": "file"})`` returns a working LocalStorage.
"""
from __future__ import annotations

import pytest

# Import triggers registration side-effect for both names
import pet_infra.storage.local  # noqa: F401
from pet_infra.registry import STORAGE
from pet_infra.storage.local import LocalStorage


class TestFileSchemeSupport:
    """LocalStorage handles file:// URIs (in addition to local://)."""

    def test_read_file_scheme(self, tmp_path) -> None:
        """LocalStorage.read() accepts ``file://`` URIs and returns correct bytes."""
        p = tmp_path / "data.bin"
        p.write_bytes(b"hello file scheme")
        storage = LocalStorage()
        assert storage.read(f"file://{p}") == b"hello file scheme"

    def test_exists_file_scheme_true(self, tmp_path) -> None:
        """exists() returns True for a file:// URI pointing to an existing file."""
        p = tmp_path / "exists.bin"
        p.write_bytes(b"x")
        storage = LocalStorage()
        assert storage.exists(f"file://{p}") is True

    def test_exists_file_scheme_false(self) -> None:
        """exists() returns False for a file:// URI pointing to a nonexistent path."""
        storage = LocalStorage()
        assert storage.exists("file:///nonexistent/path/xyz.bin") is False

    def test_write_file_scheme(self, tmp_path) -> None:
        """write() accepts ``file://`` URIs and returns the canonical ``local://`` URI."""
        storage = LocalStorage()
        uri = f"file://{tmp_path}/out.bin"
        result = storage.write(uri, b"written via file://")
        # write() returns local:// canonical form
        assert result.startswith("local://")
        assert (tmp_path / "out.bin").read_bytes() == b"written via file://"

    def test_iter_prefix_file_scheme(self, tmp_path) -> None:
        """iter_prefix() accepts ``file://`` prefix and yields local:// URIs."""
        storage = LocalStorage()
        (tmp_path / "a.bin").write_bytes(b"a")
        (tmp_path / "b.bin").write_bytes(b"b")
        results = list(storage.iter_prefix(f"file://{tmp_path}/"))
        assert len(results) >= 2
        assert all(r.startswith("local://") for r in results)


class TestStorageRegistryFileType:
    """STORAGE.build({"type": "file"}) must return a working LocalStorage."""

    def test_build_by_file_type(self) -> None:
        """STORAGE.build({'type': 'file'}) returns a LocalStorage instance."""
        from pet_infra._register import register_all

        register_all()
        obj = STORAGE.build({"type": "file"})
        assert isinstance(obj, LocalStorage)

    def test_build_by_file_type_can_read(self, tmp_path) -> None:
        """LocalStorage built via 'file' type can read a file:// URI."""
        from pet_infra._register import register_all

        register_all()
        p = tmp_path / "test.bin"
        p.write_bytes(b"registry works")
        obj = STORAGE.build({"type": "file"})
        assert obj.read(f"file://{p}") == b"registry works"

    def test_file_type_registered(self) -> None:
        """STORAGE registry contains the 'file' key after import."""
        assert "file" in STORAGE.module_dict
