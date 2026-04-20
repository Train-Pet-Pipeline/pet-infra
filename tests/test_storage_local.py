from __future__ import annotations

import pytest

# Import triggers registration side-effect
import pet_infra.storage.local  # noqa: F401
from pet_infra.registry import STORAGE
from pet_infra.storage.local import LocalStorage


class TestLocalStorageWrite:
    """Tests for LocalStorage.write()."""

    def test_write_returns_absolute_path(self, tmp_path):
        """write() returns the absolute path string of the written file."""
        storage = LocalStorage()
        uri = f"local://{tmp_path}/foo/bar.bin"
        result = storage.write(uri, b"xyz")
        assert result == str(tmp_path / "foo" / "bar.bin")

    def test_write_creates_file_with_content(self, tmp_path):
        """write() actually writes the bytes to disk."""
        storage = LocalStorage()
        uri = f"local://{tmp_path}/foo/bar.bin"
        storage.write(uri, b"xyz")
        assert (tmp_path / "foo" / "bar.bin").read_bytes() == b"xyz"

    def test_write_creates_parent_dirs(self, tmp_path):
        """write() creates parent directories if they do not exist."""
        storage = LocalStorage()
        uri = f"local://{tmp_path}/a/b/c/deep.bin"
        storage.write(uri, b"deep")
        assert (tmp_path / "a" / "b" / "c" / "deep.bin").exists()

    def test_write_raises_on_wrong_scheme(self, tmp_path):
        """write() raises ValueError for non-local:// URIs."""
        storage = LocalStorage()
        with pytest.raises(ValueError):
            storage.write("s3://bucket/key", b"data")


class TestLocalStorageRead:
    """Tests for LocalStorage.read()."""

    def test_read_returns_written_bytes(self, tmp_path):
        """read() returns the bytes previously written by write()."""
        storage = LocalStorage()
        uri = f"local://{tmp_path}/foo/bar.bin"
        storage.write(uri, b"xyz")
        assert storage.read(uri) == b"xyz"

    def test_read_raises_on_wrong_scheme(self):
        """read() raises ValueError for non-local:// URIs."""
        storage = LocalStorage()
        with pytest.raises(ValueError):
            storage.read("s3://bucket/key")


class TestLocalStorageExists:
    """Tests for LocalStorage.exists()."""

    def test_exists_true_after_write(self, tmp_path):
        """exists() returns True for a URI that has been written."""
        storage = LocalStorage()
        uri = f"local://{tmp_path}/foo/bar.bin"
        storage.write(uri, b"xyz")
        assert storage.exists(uri) is True

    def test_exists_false_for_nonexistent(self):
        """exists() returns False for a path that does not exist."""
        storage = LocalStorage()
        assert storage.exists("local:///nonexistent/path/to/nothing.bin") is False

    def test_exists_raises_on_wrong_scheme(self):
        """exists() raises ValueError for non-local:// URIs."""
        storage = LocalStorage()
        with pytest.raises(ValueError):
            storage.exists("s3://bucket/key")


class TestLocalStorageIterPrefix:
    """Tests for LocalStorage.iter_prefix()."""

    def test_iter_prefix_yields_written_files(self, tmp_path):
        """iter_prefix() yields URIs for all files under the given prefix."""
        storage = LocalStorage()
        storage.write(f"local://{tmp_path}/foo/a.bin", b"a")
        storage.write(f"local://{tmp_path}/foo/b.bin", b"b")
        results = list(storage.iter_prefix(f"local://{tmp_path}/foo/"))
        assert f"local://{tmp_path}/foo/a.bin" in results
        assert f"local://{tmp_path}/foo/b.bin" in results

    def test_iter_prefix_yields_sorted(self, tmp_path):
        """iter_prefix() yields URIs in sorted order."""
        storage = LocalStorage()
        storage.write(f"local://{tmp_path}/foo/z.bin", b"z")
        storage.write(f"local://{tmp_path}/foo/a.bin", b"a")
        storage.write(f"local://{tmp_path}/foo/m.bin", b"m")
        results = list(storage.iter_prefix(f"local://{tmp_path}/foo/"))
        assert results == sorted(results)

    def test_iter_prefix_each_result_has_local_scheme(self, tmp_path):
        """iter_prefix() wraps each path in local:// scheme."""
        storage = LocalStorage()
        storage.write(f"local://{tmp_path}/foo/bar.bin", b"data")
        results = list(storage.iter_prefix(f"local://{tmp_path}/foo/"))
        assert all(r.startswith("local://") for r in results)

    def test_iter_prefix_raises_on_wrong_scheme(self):
        """iter_prefix() raises ValueError for non-local:// URIs."""
        storage = LocalStorage()
        with pytest.raises(ValueError):
            list(storage.iter_prefix("s3://bucket/prefix/"))


class TestLocalStorageRegistration:
    """Tests for STORAGE registry integration."""

    def test_registered_under_local(self):
        """LocalStorage is registered in STORAGE under the name 'local'."""
        assert STORAGE.get("local") is LocalStorage
