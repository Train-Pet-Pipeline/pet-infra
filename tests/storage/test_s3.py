"""Tests for S3Storage backend (moto-mocked)."""
from __future__ import annotations

import pytest

# Import triggers registration side-effect
import pet_infra.storage.s3  # noqa: F401
from pet_infra.storage.s3 import S3Storage


def test_s3_scheme_attr() -> None:
    """S3Storage advertises ``s3`` as its scheme."""
    assert S3Storage.scheme == "s3"


def test_s3_round_trip(s3_bucket: dict[str, str | None]) -> None:
    """write() then read() round-trips bytes through S3, exists() reports True."""
    storage = S3Storage(endpoint_url=s3_bucket["endpoint_url"])
    bucket = s3_bucket["bucket"]
    uri = f"s3://{bucket}/round/trip.bin"
    written = storage.write(uri, b"payload-bytes")
    assert written == uri
    assert storage.exists(uri) is True
    assert storage.read(uri) == b"payload-bytes"


def test_s3_iter_prefix(s3_bucket: dict[str, str | None]) -> None:
    """iter_prefix() yields sorted full s3:// URIs for every key under the prefix."""
    storage = S3Storage(endpoint_url=s3_bucket["endpoint_url"])
    bucket = s3_bucket["bucket"]
    prefix = f"s3://{bucket}/listing/"
    storage.write(f"s3://{bucket}/listing/a.bin", b"a")
    storage.write(f"s3://{bucket}/listing/b.bin", b"b")
    storage.write(f"s3://{bucket}/listing/sub/c.bin", b"c")

    results = list(storage.iter_prefix(prefix))
    expected = [
        f"s3://{bucket}/listing/a.bin",
        f"s3://{bucket}/listing/b.bin",
        f"s3://{bucket}/listing/sub/c.bin",
    ]
    assert results == expected


def test_s3_rejects_wrong_scheme() -> None:
    """S3Storage refuses URIs whose scheme is not ``s3``."""
    storage = S3Storage()
    with pytest.raises(ValueError, match="scheme"):
        storage.read("file:///tmp/x")


def test_s3_rejects_empty_bucket() -> None:
    """S3Storage refuses ``s3://`` URIs that omit the bucket."""
    storage = S3Storage()
    with pytest.raises(ValueError, match="bucket"):
        storage.read("s3://")


def test_s3_exists_false_for_missing_key(s3_bucket: dict[str, str | None]) -> None:
    """exists() returns False (not raises) for a key that was never written."""
    storage = S3Storage(endpoint_url=s3_bucket["endpoint_url"])
    bucket = s3_bucket["bucket"]
    assert storage.exists(f"s3://{bucket}/never/written.bin") is False


def test_s3_registered_under_s3() -> None:
    """S3Storage is registered in STORAGE under the name 's3'."""
    from pet_infra.registry import STORAGE

    assert STORAGE.get("s3") is S3Storage
