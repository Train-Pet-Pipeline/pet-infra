"""Shared fixtures for pet_infra storage backend tests."""
from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def s3_bucket() -> Iterator[dict[str, str | None]]:
    """Spin up a moto-mocked S3 bucket and yield its connection info.

    Yields:
        A dict with keys:
            - ``bucket``: the bucket name created in the mock.
            - ``endpoint_url``: ``None`` (moto patches boto3 directly).
    """
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        bucket = "pet-infra-test"
        client.create_bucket(Bucket=bucket)
        yield {"bucket": bucket, "endpoint_url": None}
