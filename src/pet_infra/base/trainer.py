from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pet_schema import ExperimentRecipe, ModelCard, ResourceSpec


class BaseTrainer(ABC):
    """一个完整的训练作业 wrapper（封装 LLaMA-Factory / Lightning / etc）."""

    @abstractmethod
    def fit(
        self,
        recipe: ExperimentRecipe,
        resolved_config: dict,
        output_dir: Path,
    ) -> ModelCard:
        """Run training and return the resulting ModelCard.

        Args:
            recipe: The experiment recipe describing what to train.
            resolved_config: Fully resolved config dict (after Hydra composition).
            output_dir: Directory where model artifacts are written.

        Returns:
            ModelCard describing the trained model.
        """
        ...

    @abstractmethod
    def validate_config(self, resolved_config: dict) -> None:
        """Validate resolved config before training starts.

        Args:
            resolved_config: Fully resolved config dict to validate.

        Raises:
            ValueError: If configuration is invalid.
        """
        ...

    @abstractmethod
    def estimate_resources(self, resolved_config: dict) -> ResourceSpec:
        """Estimate compute resources required for this training job.

        Args:
            resolved_config: Fully resolved config dict.

        Returns:
            ResourceSpec describing required resources.
        """
        ...
