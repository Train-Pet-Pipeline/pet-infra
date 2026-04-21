import os
from unittest.mock import MagicMock, patch

import pytest
from tenacity import wait_none

from pet_infra.experiment_logger.clearml_logger import ClearMLLogger


@pytest.fixture
def mock_clearml():
    with patch("pet_infra.experiment_logger.clearml_logger.Task") as m:
        yield m


def test_offline_mode_calls_set_offline(mock_clearml):
    logger = ClearMLLogger(mode="offline")
    logger.start(recipe=None, stage="train")
    mock_clearml.set_offline.assert_called_once_with(True)
    mock_clearml.init.assert_called_once()


def test_saas_mode_does_not_set_offline(mock_clearml):
    logger = ClearMLLogger(mode="saas", api_host="https://api.clear.ml")
    logger.start(recipe=None, stage="train")
    mock_clearml.set_offline.assert_not_called()


def test_saas_mode_sets_clearml_api_host_env(mock_clearml, monkeypatch):
    monkeypatch.delenv("CLEARML_API_HOST", raising=False)
    logger = ClearMLLogger(mode="saas", api_host="https://api.clear.ml")
    logger.start(recipe=None, stage="train")
    assert os.environ.get("CLEARML_API_HOST") == "https://api.clear.ml"


def test_self_hosted_mode_uses_api_host(mock_clearml):
    logger = ClearMLLogger(mode="self_hosted", api_host="http://localhost:8008")
    logger.start(recipe=None, stage="train")


def test_on_unavailable_fallback_null_returns_null_logger():
    from pet_infra.experiment_logger.clearml_logger import _with_fallback
    with patch("pet_infra.experiment_logger.clearml_logger.Task") as m:
        m.init.side_effect = ConnectionError("unreachable")
        logger = _with_fallback(ClearMLLogger(mode="saas", on_unavailable="fallback_null"))
        task_id = logger.start(recipe=None, stage="train")
        assert task_id is None  # switched to NullLogger


def test_on_unavailable_strict_raises():
    with patch("pet_infra.experiment_logger.clearml_logger.Task") as m:
        m.init.side_effect = ConnectionError("unreachable")
        logger = ClearMLLogger(mode="saas", on_unavailable="strict")
        with pytest.raises(ConnectionError):
            logger.start(recipe=None, stage="train")


def test_on_unavailable_retry_3_times():
    """With retry policy, Task.init is called up to 3 times; succeeds on the 3rd."""
    fake_task = MagicMock()
    fake_task.id = "abc"
    with patch("pet_infra.experiment_logger.clearml_logger.Task") as m:
        m.init.side_effect = [ConnectionError(), ConnectionError(), fake_task]
        logger = ClearMLLogger(mode="saas", on_unavailable="retry", retry_wait=wait_none())
        task_id = logger.start(recipe=None, stage="train")
        assert task_id == "abc"
        assert m.init.call_count == 3
