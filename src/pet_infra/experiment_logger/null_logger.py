from __future__ import annotations

from typing import Literal

from pet_schema.model_card import ModelCard
from pet_schema.recipe import ExperimentRecipe

from .base import ExperimentLogger


class NullLogger(ExperimentLogger):
    """No-op logger for unit tests / scenarios requiring zero tracking."""

    def start(self, recipe: ExperimentRecipe | None, stage: str) -> str | None:
        """Start a task; always returns None."""
        return None

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        """No-op metric logging."""
        pass

    def log_artifact(self, name: str, uri: str) -> None:
        """No-op artifact logging."""
        pass

    def log_model_card(self, card: ModelCard) -> None:
        """No-op model card logging."""
        pass

    def finish(self, status: Literal["success", "failed"]) -> None:
        """No-op task finalization."""
        pass
