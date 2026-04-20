from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pet_schema import MetricResult


class BaseMetric(ABC):
    """Base class for all evaluation metrics."""

    name: ClassVar[str]
    higher_is_better: ClassVar[bool]

    @abstractmethod
    def compute(
        self,
        predictions: list,
        references: list,
        **kwargs,
    ) -> MetricResult:
        """Compute the metric over predictions vs. references.

        Args:
            predictions: List of model predictions.
            references: List of ground-truth references.
            **kwargs: Additional metric-specific arguments.

        Returns:
            MetricResult containing the computed score and metadata.
        """
        ...
