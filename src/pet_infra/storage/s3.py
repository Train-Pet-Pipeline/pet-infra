"""S3-backed storage backend (boto3)."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any, ClassVar
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

from pet_infra.base import BaseStorage
from pet_infra.registry import STORAGE


@STORAGE.register_module(name="s3")
class S3Storage(BaseStorage):
    """Amazon S3 storage backend (also compatible with S3 API endpoints).

    Handles URIs of the form ``s3://<bucket>/<key>``.
    """

    scheme: ClassVar[str] = "s3"

    def __init__(
        self,
        endpoint_url: str | None = None,
        region_name: str = "us-east-1",
        **_: Any,
    ) -> None:
        """Build a boto3 S3 client for this backend.

        Args:
            endpoint_url: Optional custom endpoint (e.g. for MinIO or moto).
                When ``None`` (default), boto3 resolves AWS endpoints normally.
            region_name: AWS region for the client.
            **_: Extra kwargs are accepted and ignored to keep the constructor
                forgiving when instantiated via Hydra/registry configs.
        """
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region_name,
        )

    def _split(self, uri: str) -> tuple[str, str]:
        """Parse an ``s3://`` URI into its (bucket, key) parts.

        Args:
            uri: A URI with ``s3://`` scheme.

        Returns:
            A ``(bucket, key)`` tuple where ``key`` has no leading slash.

        Raises:
            ValueError: If the URI scheme is not ``s3``.
        """
        parsed = urlparse(uri)
        if parsed.scheme != self.scheme:
            raise ValueError(f"S3Storage cannot handle scheme={parsed.scheme!r}")
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        return bucket, key

    def read(self, uri: str) -> bytes:
        """Read and return raw bytes from the given S3 URI.

        Args:
            uri: An ``s3://`` URI pointing to the object to read.

        Returns:
            Raw bytes content of the S3 object.
        """
        bucket, key = self._split(uri)
        obj = self._client.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()

    def write(self, uri: str, data: bytes) -> str:
        """Upload data to the given S3 URI.

        Args:
            uri: An ``s3://`` URI pointing to the target object.
            data: Raw bytes to upload.

        Returns:
            The canonical ``s3://`` URI where the data was written.
        """
        bucket, key = self._split(uri)
        self._client.put_object(Bucket=bucket, Key=key, Body=data)
        return f"{self.scheme}://{bucket}/{key}"

    def exists(self, uri: str) -> bool:
        """Check whether an object exists at the given S3 URI.

        Args:
            uri: An ``s3://`` URI to check.

        Returns:
            True if the object exists, False if it is missing.

        Raises:
            ClientError: For any S3 error other than a missing-object signal.
        """
        bucket, key = self._split(uri)
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def iter_prefix(self, prefix: str) -> Iterator[str]:
        """Iterate over every object URI under the given S3 prefix.

        Args:
            prefix: An ``s3://`` URI prefix to list (e.g. ``s3://bucket/dir/``).

        Yields:
            ``s3://`` URIs for every object found under the prefix, in the
            order returned by S3 ``list_objects_v2`` (lexicographic by key).
        """
        bucket, key_prefix = self._split(prefix)
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=key_prefix):
            for item in page.get("Contents", []) or []:
                yield f"{self.scheme}://{bucket}/{item['Key']}"
