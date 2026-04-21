from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any

from .base import ExperimentLogger
from .null_logger import NullLogger

_BUILTINS: dict[str, type[ExperimentLogger]] = {"null": NullLogger}


def build_experiment_logger(cfg: dict[str, Any]) -> ExperimentLogger:
    """Instantiate an ExperimentLogger by name from cfg.

    Looks up built-ins first, then falls back to the ``pet_infra.experiment_loggers``
    entry-point group for third-party plugins.

    Args:
        cfg: Mapping with at least ``name`` key. All other keys are forwarded
             as constructor kwargs for plugin loggers.

    Returns:
        An instantiated ExperimentLogger.

    Raises:
        KeyError: When no built-in or installed plugin matches the requested name.
    """
    name = cfg.get("name", "null")
    if name in _BUILTINS:
        return _BUILTINS[name]()
    for ep in entry_points(group="pet_infra.experiment_loggers"):
        if ep.name == name:
            try:
                cls = ep.load()
            except Exception as e:
                raise RuntimeError(
                    f"failed to load experiment logger plugin '{name}'"
                    f" from entry-point '{ep.value}'"
                ) from e
            return cls(**{k: v for k, v in cfg.items() if k != "name"})
    raise KeyError(f"unknown experiment logger: {name}")
