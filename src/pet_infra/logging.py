"""JSON structured logging for all pet-pipeline repos.

Usage:
    from pet_infra.logging import get_logger
    logger = get_logger("pet-data")
    logger.info("frame_processed", extra={"frame_id": "abc", "confidence": 0.95})

Output:
    {"ts": "2026-04-15T10:30:00+00:00", "level": "INFO", "repo": "pet-data",
     "event": "frame_processed", "frame_id": "abc", "confidence": 0.95}
"""

from __future__ import annotations

import datetime
import json
import logging
import sys
from typing import Any


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON with standardized fields."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""
        log_data: dict[str, Any] = {
            "ts": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc  # noqa: UP017 — 3.10 compat
            ).isoformat(),
            "level": record.levelname,
            "repo": record.name,
            "event": record.getMessage(),
        }
        _internal = {
            "name", "msg", "args", "created", "relativeCreated",
            "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "filename", "module", "pathname", "thread", "threadName",
            "processName", "process", "levelname", "levelno", "message",
            "msecs", "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in _internal and not key.startswith("_"):
                log_data[key] = value
        if record.exc_info and record.exc_info[1]:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, default=str, ensure_ascii=False)


def setup_logging(repo: str, level: str = "INFO") -> logging.Logger:
    """Configure and return a JSON logger for the given repo.

    Args:
        repo: Repository name (e.g. "pet-data"). Used as logger name and
              appears in the "repo" field of each log record.
        level: Log level string. Defaults to "INFO".

    Returns:
        Configured logger instance. Idempotent — calling twice with the
        same repo returns the same logger without duplicating handlers.
    """
    logger = logging.getLogger(repo)
    for handler in logger.handlers:
        if isinstance(handler.formatter, JSONFormatter):
            return logger
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    return logger


def get_logger(repo: str, level: str = "INFO") -> logging.Logger:
    """Convenience alias for setup_logging.

    Args:
        repo: Repository name.
        level: Log level string. Defaults to "INFO".

    Returns:
        Configured logger instance.
    """
    return setup_logging(repo, level)
