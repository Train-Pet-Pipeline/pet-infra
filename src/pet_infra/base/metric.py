from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, ClassVar

from pet_schema import MetricResult


class BaseMetric(ABC):
    """Base class for all evaluation metrics."""

    name: ClassVar[str]
    higher_is_better: ClassVar[bool]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # skip abstract intermediates
        if getattr(cls, "__abstractmethods__", None):
            return
        for attr in ("name", "higher_is_better"):
            if not hasattr(cls, attr):
                raise TypeError(
                    f"Subclass {cls.__name__} must define ClassVar '{attr}'"
                )

    @abstractmethod
    def compute(
        self,
        predictions: Sequence[Any],
        references: Sequence[Any],
        **kwargs: Any,
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
