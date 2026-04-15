"""Tests for pet_infra.logging module."""

import json
import logging
import sys

from pet_infra.logging import JSONFormatter, get_logger, setup_logging


class TestSetupLogging:
    def test_setup_logging_returns_logger(self):
        logger = setup_logging("test-repo")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test-repo"

    def test_setup_logging_sets_json_handler(self):
        logger = setup_logging("test-repo-handler")
        handlers = [h for h in logger.handlers if isinstance(h.formatter, JSONFormatter)]
        assert len(handlers) >= 1

    def test_setup_logging_idempotent(self):
        logger1 = setup_logging("test-repo-idempotent")
        count1 = len(logger1.handlers)
        logger2 = setup_logging("test-repo-idempotent")
        count2 = len(logger2.handlers)
        assert count1 == count2
        assert logger1 is logger2


class TestGetLogger:
    def test_get_logger_returns_configured_logger(self):
        logger = get_logger("test-get")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_same_name_returns_same_instance(self):
        logger1 = get_logger("test-same")
        logger2 = get_logger("test-same")
        assert logger1 is logger2


class TestJSONOutput:
    def test_log_output_is_valid_json(self, capfd):
        logger = logging.getLogger("test-json-unique1")
        logger.handlers.clear()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.info("test_event", extra={"key": "value"})
        captured = capfd.readouterr()
        record = json.loads(captured.out.strip())

        assert record["event"] == "test_event"
        assert record["level"] == "INFO"
        assert record["key"] == "value"
        assert "ts" in record

    def test_log_output_includes_repo_field(self, capfd):
        logger = logging.getLogger("my-repo-unique1")
        logger.handlers.clear()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.info("event")
        captured = capfd.readouterr()
        record = json.loads(captured.out.strip())
        assert record["repo"] == "my-repo-unique1"
