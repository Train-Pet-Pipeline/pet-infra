from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pet_schema.model_card import ModelCard


class ExperimentLogger(ABC):
    """Cross-stage experiment tracking ABC. Pluggable via entry-points."""

    @abstractmethod
    def start(self, recipe, stage: str) -> str | None:
        """Start a task. Returns task_id (None for loggers without identity)."""

    @abstractmethod
    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        """Log scalar metrics at an optional step index."""

    @abstractmethod
    def log_artifact(self, name: str, uri: str) -> None:
        """Record an artifact by name and URI."""

    @abstractmethod
    def log_model_card(self, card: ModelCard) -> None:
        """Attach a ModelCard to the current task."""

    @abstractmethod
    def finish(self, status: Literal["success", "failed"]) -> None:
        """Finalize the task with the given status."""
